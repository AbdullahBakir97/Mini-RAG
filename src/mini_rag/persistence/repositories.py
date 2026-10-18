"""SQLAlchemy implementations of the domain repository interfaces."""

import json
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Interval,
    String,
    and_,
    any_,
    bindparam,
    delete,
    func,
    insert,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from mini_rag.domain.models import (
    AnswerRecord,
    Chunk,
    Conversation,
    ConversationMessage,
    Feedback,
    FeedbackCounts,
    FileRecord,
    Job,
    JobStage,
    JobStatus,
    Project,
    RatedAnswer,
    ScoredChunk,
    SearchFilters,
    StoredCitation,
    UnembeddedChunk,
    UsageTotals,
    Webhook,
    WebhookDelivery,
)

from .tables import (
    FULL_TEXT_CONFIG,
    AnswerRow,
    ChunkRow,
    ConversationMessageRow,
    ConversationRow,
    FileRow,
    JobRow,
    ProjectRow,
    WebhookDeliveryRow,
    WebhookRow,
)


def _project(row: ProjectRow) -> Project:
    return Project(id=row.id, name=row.name, created_at=row.created_at)


def _file(row: FileRow) -> FileRecord:
    return FileRecord(id=row.id, project_id=row.project_id, key=row.key,
                      original_name=row.original_name, content_type=row.content_type,
                      size_bytes=row.size_bytes, created_at=row.created_at,
                      content_sha256=row.content_sha256)


def _chunk(row: ChunkRow) -> Chunk:
    return Chunk(index=row.chunk_index, text=row.text, metadata=row.meta)


# Hybrid search: how many results each list contributes, per result wanted
# and at least, and the RRF constant (60 is the usual choice). Searches with
# max_per_file fetch more results, up to MAX_FETCHED, and drop some.
CANDIDATES_PER_RESULT = 4
MIN_CANDIDATES = 20
MAX_FETCHED = 200
RRF_K = 60

class SqlProjectRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_name(self, name: str) -> Project | None:
        row = await self.session.scalar(select(ProjectRow).where(ProjectRow.name == name))
        return _project(row) if row else None

    async def get_or_create(self, name: str) -> Project:
        # INSERT ... ON CONFLICT DO NOTHING avoids a race between two
        # requests creating the same project.
        await self.session.execute(
            pg_insert(ProjectRow).values(name=name).on_conflict_do_nothing(index_elements=["name"]))
        project = await self.get_by_name(name)
        if project is None:  # only possible if it was deleted concurrently
            raise RuntimeError(f"Project {name!r} vanished while being created")
        return project

    async def list_all(self, *, offset: int, limit: int) -> list[Project]:
        rows = await self.session.scalars(
            select(ProjectRow).order_by(ProjectRow.name).offset(offset).limit(limit))
        return [_project(row) for row in rows]

    async def count(self) -> int:
        return await self.session.scalar(select(func.count()).select_from(ProjectRow))

    async def delete(self, name: str) -> bool:
        # Files, chunks, answers and conversations go with it (ON DELETE CASCADE).
        result = await self.session.execute(delete(ProjectRow).where(ProjectRow.name == name))
        return result.rowcount > 0


class SqlFileRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, *, project_id: int, key: str, original_name: str,
                  content_type: str, size_bytes: int,
                  content_sha256: str | None = None) -> FileRecord | None:
        # Two uploads of the same content at once: one is recorded, the other gets None.
        row = await self.session.scalar(
            pg_insert(FileRow)
            .values(project_id=project_id, key=key, original_name=original_name,
                    content_type=content_type, size_bytes=size_bytes,
                    content_sha256=content_sha256)
            .on_conflict_do_nothing(index_elements=["project_id", "content_sha256"],
                                    index_where=FileRow.content_sha256.is_not(None))
            .returning(FileRow))
        return _file(row) if row else None

    async def get_by_content(self, project_id: int, content_sha256: str) -> FileRecord | None:
        row = await self.session.scalar(
            select(FileRow).where(FileRow.project_id == project_id,
                                  FileRow.content_sha256 == content_sha256))
        return _file(row) if row else None

    async def delete(self, project_id: int, key: str) -> bool:
        # Its chunks go with it (ON DELETE CASCADE).
        result = await self.session.execute(
            delete(FileRow).where(FileRow.project_id == project_id, FileRow.key == key))
        return result.rowcount > 0

    async def get_by_key(self, project_id: int, key: str) -> FileRecord | None:
        row = await self.session.scalar(
            select(FileRow).where(FileRow.project_id == project_id, FileRow.key == key))
        return _file(row) if row else None

    async def list_for_project(self, project_id: int, *, offset: int,
                               limit: int) -> list[FileRecord]:
        rows = await self.session.scalars(
            select(FileRow).where(FileRow.project_id == project_id)
            .order_by(FileRow.created_at, FileRow.id).offset(offset).limit(limit))
        return [_file(row) for row in rows]

    async def count_for_project(self, project_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(FileRow).where(FileRow.project_id == project_id))


class SqlChunkRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def replace_for_file(self, file: FileRecord, chunks: Sequence[Chunk]) -> None:
        await self.session.execute(delete(ChunkRow).where(ChunkRow.file_id == file.id))
        if chunks:
            await self.session.execute(insert(ChunkRow), [
                {"file_id": file.id, "project_id": file.project_id,
                 "chunk_index": chunk.index, "text": chunk.text, "meta": chunk.metadata}
                for chunk in chunks
            ])

    async def list_for_file(self, file_id: int, *, offset: int, limit: int) -> list[Chunk]:
        rows = await self.session.scalars(
            select(ChunkRow).where(ChunkRow.file_id == file_id)
            .order_by(ChunkRow.chunk_index).offset(offset).limit(limit))
        return [_chunk(row) for row in rows]

    async def count_for_file(self, file_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(ChunkRow).where(ChunkRow.file_id == file_id))

    async def count_for_project(self, project_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(ChunkRow).where(ChunkRow.project_id == project_id))

    async def list_unembedded(self, project_id: int, *, file_id: int | None,
                              limit: int) -> list[UnembeddedChunk]:
        query = select(ChunkRow.id, ChunkRow.text).where(
            ChunkRow.project_id == project_id, ChunkRow.embedding.is_(None))
        if file_id is not None:
            query = query.where(ChunkRow.file_id == file_id)
        rows = await self.session.execute(query.order_by(ChunkRow.id).limit(limit))
        return [UnembeddedChunk(id=row.id, text=row.text) for row in rows]

    async def set_embeddings(self, embeddings: Mapping[int, Sequence[float]]) -> None:
        if not embeddings:
            return
        # A plain UPDATE per ID: unlike the ORM's bulk update, it does not
        # fail when a chunk was deleted meanwhile (e.g. by reprocessing).
        table = ChunkRow.__table__
        await self.session.execute(
            update(table).where(table.c.id == bindparam("chunk_id"))
            .values(embedding=bindparam("vector")),
            [{"chunk_id": chunk_id, "vector": list(vector)}
             for chunk_id, vector in embeddings.items()])

    async def count_embedded_for_project(self, project_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(ChunkRow)
            .where(ChunkRow.project_id == project_id, ChunkRow.embedding.is_not(None)))

    async def search(self, project_id: int, embedding: Sequence[float], *, top_k: int,
                     min_score: float | None, query: str | None = None,
                     filters: SearchFilters | None = None) -> list[ScoredChunk]:
        # The HNSW index finds neighbours across all projects; filtering by
        # project afterwards could leave fewer than top_k. An iterative scan
        # (pgvector 0.8+) keeps searching until enough rows pass the filter.
        # It may return them slightly out of order, so the outer query sorts
        # them again. SET LOCAL lasts until the end of this transaction.
        await self.session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
        per_file = filters.max_per_file if filters else None
        # Results crowding into one file are dropped below, so ask for more.
        wanted = top_k if per_file is None else min(top_k * CANDIDATES_PER_RESULT, MAX_FETCHED)
        params: dict[str, Any] = {"embedding": list(embedding), "project_id": project_id,
                                  "wanted": wanted}
        narrowed = _filter_sql(filters, params)
        threshold = ""
        if min_score is not None:
            threshold = "AND 1 - (c.embedding <=> :embedding) >= :min_score"
            params["min_score"] = min_score
        if query is None:
            statement = self._vector_sql(narrowed, threshold)
        else:
            params.update(query=query, rrf_k=RRF_K,
                          candidates=max(wanted * CANDIDATES_PER_RESULT, MIN_CANDIDATES))
            statement = self._hybrid_sql(narrowed, threshold)
        rows = await self.session.execute(
            text(statement).bindparams(bindparam("embedding", type_=Vector())), params)
        hits = [ScoredChunk(file_key=row.key, score=row.similarity,
                            chunk=Chunk(index=row.chunk_index, text=row.text, metadata=row.meta))
                for row in rows]
        return _at_most_per_file(hits, per_file, top_k)

    @staticmethod
    def _vector_sql(narrowed: str, threshold: str) -> str:
        return f"""
            WITH nearest AS MATERIALIZED (
                SELECT c.id, c.file_id, c.chunk_index, c.text, c.metadata AS meta,
                       c.embedding <=> :embedding AS distance
                FROM chunks c
                WHERE c.project_id = :project_id AND c.embedding IS NOT NULL {narrowed}
                ORDER BY c.embedding <=> :embedding LIMIT :wanted
            )
            SELECT n.chunk_index, n.text, n.meta, f.key, 1 - n.distance AS similarity
            FROM nearest n JOIN files f ON f.id = n.file_id
            JOIN chunks c ON c.id = n.id
            WHERE TRUE {threshold}
            ORDER BY n.distance, n.id
        """

    @staticmethod
    def _hybrid_sql(narrowed: str, threshold: str) -> str:
        """Vector and full-text results, merged by reciprocal rank fusion.

        Each list contributes 1 / (RRF_K + rank) per chunk, so a chunk near
        the top of both wins, and the two lists' scores, which are not
        comparable, never need to be. The full-text query matches any of
        the question's words, not all of them.
        """
        return f"""
            WITH nearest_rows AS MATERIALIZED (
                SELECT c.id, c.embedding <=> :embedding AS distance FROM chunks c
                WHERE c.project_id = :project_id AND c.embedding IS NOT NULL {narrowed}
                ORDER BY c.embedding <=> :embedding LIMIT :candidates
            ), nearest AS (
                SELECT id, row_number() OVER (ORDER BY distance, id) AS rank FROM nearest_rows
            ), words AS (
                SELECT replace(plainto_tsquery('{FULL_TEXT_CONFIG}', :query)::text, '&', '|')
                       ::tsquery AS q
            ), matching AS (
                SELECT c.id, row_number() OVER (
                           ORDER BY ts_rank_cd(c.search_vector, words.q) DESC, c.id) AS rank
                FROM chunks c, words
                WHERE c.project_id = :project_id AND c.embedding IS NOT NULL
                      AND c.search_vector @@ words.q {narrowed}
                ORDER BY rank LIMIT :candidates
            ), fused AS (
                SELECT id, sum(1.0 / (:rrf_k + rank)) AS score
                FROM (SELECT * FROM nearest UNION ALL SELECT * FROM matching) ranked
                GROUP BY id
            )
            SELECT c.chunk_index, c.text, c.metadata AS meta, f.key,
                   1 - (c.embedding <=> :embedding) AS similarity
            FROM fused JOIN chunks c ON c.id = fused.id JOIN files f ON f.id = c.file_id
            WHERE TRUE {threshold}
            ORDER BY fused.score DESC, similarity DESC, c.id
            LIMIT :wanted
        """


def _filter_sql(filters: SearchFilters | None, params: dict[str, Any]) -> str:
    """Conditions on chunks ``c`` for ``filters``, adding their values to ``params``."""
    if filters is None:
        return ""
    conditions = []
    files = []
    if filters.file_keys:
        files.append("files.key = ANY(:file_keys)")
        params["file_keys"] = list(filters.file_keys)
    if filters.uploaded_after is not None:
        files.append("files.created_at >= :uploaded_after")
        params["uploaded_after"] = filters.uploaded_after
    if filters.uploaded_before is not None:
        files.append("files.created_at < :uploaded_before")
        params["uploaded_before"] = filters.uploaded_before
    if files:
        conditions.append("c.file_id IN (SELECT files.id FROM files WHERE "
                          "files.project_id = :project_id AND " + " AND ".join(files) + ")")
    # Chunks without a page (not from a PDF) have no page in range.
    if filters.page_from is not None:
        conditions.append("(c.metadata->>'page')::int >= :page_from")
        params["page_from"] = filters.page_from
    if filters.page_to is not None:
        conditions.append("(c.metadata->>'page')::int <= :page_to")
        params["page_to"] = filters.page_to
    if filters.metadata:
        conditions.append("c.metadata @> CAST(:metadata AS jsonb)")
        params["metadata"] = json.dumps(dict(filters.metadata))
    return "".join(f" AND {condition}" for condition in conditions)


def _at_most_per_file(hits: list[ScoredChunk], per_file: int | None,
                      top_k: int) -> list[ScoredChunk]:
    if per_file is None:
        return hits[:top_k]
    kept, counts = [], Counter()
    for hit in hits:
        if counts[hit.file_key] < per_file:
            kept.append(hit)
            counts[hit.file_key] += 1
    return kept[:top_k]


class SqlAnswerRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, record: AnswerRecord) -> None:
        await self.session.execute(insert(AnswerRow).values(
            project_id=record.project_id, prompt_version=record.prompt_version,
            model=record.model, streamed=record.streamed, answered=record.answered,
            input_tokens=record.input_tokens, output_tokens=record.output_tokens,
            cost_usd=record.cost_usd))

    async def totals_for_project(self, project_id: int) -> UsageTotals:
        row = (await self.session.execute(
            select(
                func.count().label("answers"),
                func.count().filter(AnswerRow.answered).label("answered"),
                func.coalesce(func.sum(AnswerRow.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AnswerRow.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(AnswerRow.cost_usd), 0).label("cost_usd"),
                func.count().filter(AnswerRow.model.is_not(None),
                                    AnswerRow.cost_usd.is_(None)).label("unpriced_answers"),
            ).where(AnswerRow.project_id == project_id))).one()
        return UsageTotals(answers=row.answers, answered=row.answered,
                           input_tokens=row.input_tokens, output_tokens=row.output_tokens,
                           cost_usd=float(row.cost_usd), unpriced_answers=row.unpriced_answers)


def _conversation(row: ConversationRow) -> Conversation:
    return Conversation(id=row.id, project_id=row.project_id, title=row.title,
                        created_at=row.created_at, updated_at=row.updated_at)


def _feedback(row: ConversationMessageRow) -> Feedback | None:
    if row.feedback_rating is None:
        return None
    return Feedback(rating=row.feedback_rating, comment=row.feedback_comment,
                    created_at=row.feedback_at)


def _message(row: ConversationMessageRow) -> ConversationMessage:
    return ConversationMessage(
        role=row.role, content=row.content,
        citations=[StoredCitation(**citation) for citation in row.citations],
        prompt_version=row.prompt_version, search_question=row.search_question,
        created_at=row.created_at, id=row.id, feedback=_feedback(row))


class SqlConversationRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: int, title: str | None) -> Conversation:
        row = await self.session.scalar(
            insert(ConversationRow)
            .values(id=str(uuid.uuid4()), project_id=project_id, title=title)
            .returning(ConversationRow))
        return _conversation(row)

    async def get(self, project_id: int, conversation_id: str) -> Conversation | None:
        row = await self.session.scalar(
            select(ConversationRow).where(ConversationRow.id == conversation_id,
                                          ConversationRow.project_id == project_id))
        return _conversation(row) if row else None

    async def list_for_project(self, project_id: int, *, offset: int,
                               limit: int) -> list[Conversation]:
        rows = await self.session.scalars(
            select(ConversationRow).where(ConversationRow.project_id == project_id)
            .order_by(ConversationRow.updated_at.desc(), ConversationRow.id)
            .offset(offset).limit(limit))
        return [_conversation(row) for row in rows]

    async def count_for_project(self, project_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(ConversationRow)
            .where(ConversationRow.project_id == project_id))

    async def delete(self, project_id: int, conversation_id: str) -> bool:
        result = await self.session.execute(
            delete(ConversationRow).where(ConversationRow.id == conversation_id,
                                          ConversationRow.project_id == project_id))
        return result.rowcount > 0

    async def messages(self, conversation_id: str, *,
                       last: int | None = None) -> list[ConversationMessage]:
        query = (select(ConversationMessageRow)
                 .where(ConversationMessageRow.conversation_id == conversation_id)
                 .order_by(ConversationMessageRow.id.desc()))
        if last is not None:
            query = query.limit(last)
        rows = list(await self.session.scalars(query))
        return [_message(row) for row in reversed(rows)]

    async def add_messages(self, conversation_id: str, messages: Sequence[ConversationMessage],
                           *, title: str | None = None) -> list[int]:
        ids = []
        # One insert per message keeps their ids in order.
        for message in messages:
            ids.append(await self.session.scalar(
                insert(ConversationMessageRow).values(
                    conversation_id=conversation_id, role=message.role, content=message.content,
                    citations=[asdict(citation) for citation in message.citations],
                    prompt_version=message.prompt_version,
                    search_question=message.search_question)
                .returning(ConversationMessageRow.id)))
        values: dict = {"updated_at": func.now()}
        if title is not None:
            values["title"] = title
        await self.session.execute(
            update(ConversationRow).where(ConversationRow.id == conversation_id).values(**values))
        return ids

    async def get_message(self, conversation_id: str,
                          message_id: int) -> ConversationMessage | None:
        row = await self.session.scalar(
            select(ConversationMessageRow).where(
                ConversationMessageRow.id == message_id,
                ConversationMessageRow.conversation_id == conversation_id))
        return _message(row) if row else None

    async def set_feedback(self, message_id: int, feedback: Feedback | None) -> None:
        await self.session.execute(
            update(ConversationMessageRow).where(ConversationMessageRow.id == message_id).values(
                feedback_rating=feedback.rating if feedback else None,
                feedback_comment=feedback.comment if feedback else None,
                feedback_at=func.now() if feedback else None))

    async def rated_answers(self, project_id: int, *, rating: str | None, offset: int,
                            limit: int) -> list[RatedAnswer]:
        answer = ConversationMessageRow
        question = aliased(ConversationMessageRow)
        # The question an answer answers: the conversation's last question before it.
        asked = (select(question.content)
                 .where(question.conversation_id == answer.conversation_id,
                        question.role == "user", question.id < answer.id)
                 .order_by(question.id.desc()).limit(1)
                 .correlate(answer).scalar_subquery())
        query = (select(answer, asked)
                 .join(ConversationRow, ConversationRow.id == answer.conversation_id)
                 .where(*self._rated(project_id, rating))
                 .order_by(answer.feedback_at.desc(), answer.id.desc())
                 .offset(offset).limit(limit))
        rows = await self.session.execute(query)
        return [RatedAnswer(conversation_id=row.conversation_id, message_id=row.id,
                            question=asked_text or "", answer=row.content,
                            citations=[StoredCitation(**c) for c in row.citations],
                            feedback=_feedback(row))
                for row, asked_text in rows]

    async def count_feedback(self, project_id: int) -> FeedbackCounts:
        rows = await self.session.execute(
            select(ConversationMessageRow.feedback_rating, func.count())
            .join(ConversationRow, ConversationRow.id == ConversationMessageRow.conversation_id)
            .where(*self._rated(project_id, None))
            .group_by(ConversationMessageRow.feedback_rating))
        counts = dict(rows.all())
        return FeedbackCounts(up=counts.get("up", 0), down=counts.get("down", 0))

    @staticmethod
    def _rated(project_id: int, rating: str | None) -> list:
        conditions = [ConversationRow.project_id == project_id,
                      ConversationMessageRow.feedback_rating.is_not(None)]
        if rating is not None:
            conditions.append(ConversationMessageRow.feedback_rating == rating)
        return conditions


def _job(row: JobRow, project_name: str, file_key: str) -> Job:
    return Job(id=row.id, project_id=row.project_id, project_name=project_name,
               file_id=row.file_id, file_key=file_key, chunk_size=row.chunk_size,
               overlap_size=row.overlap_size, status=row.status, attempts=row.attempts,
               max_attempts=row.max_attempts, created_at=row.created_at, stage=row.stage,
               progress=row.progress, chunks_count=row.chunks_count,
               error_signal=row.error_signal, started_at=row.started_at, finished_at=row.finished_at)


def _lease(seconds: int):
    return func.now() + bindparam("lease", timedelta(seconds=seconds), type_=Interval)


class SqlJobRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    def _select(self):
        return (select(JobRow, ProjectRow.name, FileRow.key)
                .join(ProjectRow, ProjectRow.id == JobRow.project_id)
                .join(FileRow, FileRow.id == JobRow.file_id))

    async def _by_id(self, job_id: str) -> Job | None:
        row = (await self.session.execute(self._select().where(JobRow.id == job_id))).first()
        return _job(*row) if row else None

    async def add(self, *, project_id: int, file_id: int, chunk_size: int, overlap_size: int,
                  max_attempts: int) -> Job:
        job_id = await self.session.scalar(
            insert(JobRow).values(id=str(uuid.uuid4()), project_id=project_id, file_id=file_id,
                                  chunk_size=chunk_size, overlap_size=overlap_size,
                                  max_attempts=max_attempts)
            .returning(JobRow.id))
        return await self._by_id(job_id)

    async def get(self, project_id: int, job_id: str) -> Job | None:
        row = (await self.session.execute(
            self._select().where(JobRow.id == job_id, JobRow.project_id == project_id))).first()
        return _job(*row) if row else None

    async def list_for_project(self, project_id: int, *, status: JobStatus | None, offset: int,
                               limit: int) -> list[Job]:
        query = self._select().where(*self._in_project(project_id, status))
        rows = await self.session.execute(
            query.order_by(JobRow.created_at.desc(), JobRow.id).offset(offset).limit(limit))
        return [_job(*row) for row in rows]

    async def count_for_project(self, project_id: int, *, status: JobStatus | None) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(JobRow).where(*self._in_project(project_id, status)))

    @staticmethod
    def _in_project(project_id: int, status: JobStatus | None) -> list:
        conditions = [JobRow.project_id == project_id]
        if status is not None:
            conditions.append(JobRow.status == status)
        return conditions

    async def claim(self, lease_seconds: int) -> Job | None:
        due = (
            select(JobRow.id)
            .where(or_(
                and_(JobRow.status == "queued", JobRow.run_after <= func.now()),
                and_(JobRow.status == "running", JobRow.locked_until < func.now(),
                     JobRow.attempts < JobRow.max_attempts)))
            .order_by(JobRow.run_after, JobRow.created_at)
            .limit(1)
            # Workers skip the rows another is claiming, rather than wait for them.
            .with_for_update(skip_locked=True)
            .scalar_subquery())
        job_id = await self.session.scalar(
            update(JobRow).where(JobRow.id == due)
            .values(status="running", attempts=JobRow.attempts + 1, stage="processing",
                    progress=0, started_at=func.now(), locked_until=_lease(lease_seconds))
            .returning(JobRow.id))
        return await self._by_id(job_id) if job_id else None

    async def fail_abandoned(self) -> int:
        result = await self.session.execute(
            update(JobRow)
            .where(JobRow.status == "running", JobRow.locked_until < func.now(),
                   JobRow.attempts >= JobRow.max_attempts)
            .values(status="failed", finished_at=func.now(), locked_until=None,
                    error_signal="job_abandoned"))
        return result.rowcount

    async def set_progress(self, job_id: str, stage: JobStage, progress: float,
                           lease_seconds: int) -> None:
        await self.session.execute(
            update(JobRow).where(JobRow.id == job_id, JobRow.status == "running")
            .values(stage=stage, progress=progress, locked_until=_lease(lease_seconds)))

    async def succeed(self, job_id: str, chunks_count: int) -> None:
        await self.session.execute(
            update(JobRow).where(JobRow.id == job_id)
            .values(status="succeeded", progress=1, chunks_count=chunks_count,
                    error_signal=None, locked_until=None, finished_at=func.now()))

    async def fail(self, job_id: str, signal: str, retry_at: datetime | None) -> None:
        values = {"error_signal": signal, "locked_until": None}
        if retry_at is None:
            values |= {"status": "failed", "finished_at": func.now()}
        else:
            values |= {"status": "queued", "run_after": retry_at}
        await self.session.execute(update(JobRow).where(JobRow.id == job_id).values(**values))

    async def release(self, job_id: str) -> None:
        await self.session.execute(
            update(JobRow).where(JobRow.id == job_id, JobRow.status == "running")
            .values(status="queued", attempts=JobRow.attempts - 1, stage=None, progress=0,
                    locked_until=None, run_after=func.now()))

    async def requeue(self, job_id: str) -> None:
        await self.session.execute(
            update(JobRow).where(JobRow.id == job_id, JobRow.status == "failed")
            .values(status="queued", attempts=0, stage=None, progress=0, chunks_count=None,
                    error_signal=None, run_after=func.now(),
                    started_at=None, finished_at=None))


def _webhook(row: WebhookRow) -> Webhook:
    return Webhook(id=row.id, project_id=row.project_id, url=row.url, events=tuple(row.events),
                   secret=row.secret, created_at=row.created_at, description=row.description)


def _delivery(row: WebhookDeliveryRow) -> WebhookDelivery:
    return WebhookDelivery(id=row.id, webhook_id=row.webhook_id, event=row.event,
                           payload=row.payload, status=row.status, attempts=row.attempts,
                           created_at=row.created_at, next_attempt_at=row.next_attempt_at,
                           response_status=row.response_status, error=row.error,
                           delivered_at=row.delivered_at)


class SqlWebhookRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, project_id: int, url: str, events: Sequence[str], secret: str,
                     description: str | None) -> Webhook:
        row = await self.session.scalar(
            insert(WebhookRow).values(id=str(uuid.uuid4()), project_id=project_id, url=url,
                                      events=list(events), secret=secret,
                                      description=description)
            .returning(WebhookRow))
        return _webhook(row)

    async def get(self, project_id: int, webhook_id: str) -> Webhook | None:
        row = await self.session.scalar(
            select(WebhookRow).where(WebhookRow.id == webhook_id,
                                     WebhookRow.project_id == project_id))
        return _webhook(row) if row else None

    async def list_for_project(self, project_id: int, *, offset: int,
                               limit: int) -> list[Webhook]:
        rows = await self.session.scalars(
            select(WebhookRow).where(WebhookRow.project_id == project_id)
            .order_by(WebhookRow.created_at, WebhookRow.id).offset(offset).limit(limit))
        return [_webhook(row) for row in rows]

    async def count_for_project(self, project_id: int) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(WebhookRow)
            .where(WebhookRow.project_id == project_id))

    async def delete(self, project_id: int, webhook_id: str) -> bool:
        result = await self.session.execute(
            delete(WebhookRow).where(WebhookRow.id == webhook_id,
                                     WebhookRow.project_id == project_id))
        return result.rowcount > 0

    async def enqueue(self, project_id: int, event: str, payload: Mapping[str, Any]) -> int:
        subscribed = select(
            func.gen_random_uuid(), WebhookRow.id, bindparam("event", event, type_=String),
            bindparam("payload", dict(payload), type_=JSONB),
        ).where(WebhookRow.project_id == project_id,
                bindparam("wanted", event, type_=String) == any_(WebhookRow.events))
        result = await self.session.execute(
            insert(WebhookDeliveryRow)
            .from_select(["id", "webhook_id", "event", "payload"], subscribed))
        return result.rowcount

    async def add_delivery(self, webhook_id: str, event: str,
                           payload: Mapping[str, Any]) -> WebhookDelivery:
        row = await self.session.scalar(
            insert(WebhookDeliveryRow).values(id=str(uuid.uuid4()), webhook_id=webhook_id,
                                              event=event, payload=dict(payload))
            .returning(WebhookDeliveryRow))
        return _delivery(row)

    async def claim_delivery(self, lease_seconds: int) -> tuple[WebhookDelivery, Webhook] | None:
        due = (
            select(WebhookDeliveryRow.id)
            .where(WebhookDeliveryRow.status == "pending",
                   WebhookDeliveryRow.next_attempt_at <= func.now())
            .order_by(WebhookDeliveryRow.next_attempt_at, WebhookDeliveryRow.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery())
        row = await self.session.scalar(
            update(WebhookDeliveryRow).where(WebhookDeliveryRow.id == due)
            .values(attempts=WebhookDeliveryRow.attempts + 1,
                    next_attempt_at=_lease(lease_seconds))
            .returning(WebhookDeliveryRow))
        if row is None:
            return None
        webhook = await self.session.get(WebhookRow, row.webhook_id)
        return _delivery(row), _webhook(webhook)

    async def record_attempt(self, delivery_id: str, *, delivered: bool,
                             response_status: int | None, error: str | None,
                             retry_at: datetime | None) -> None:
        values: dict[str, Any] = {"response_status": response_status, "error": error}
        if delivered:
            values |= {"status": "delivered", "delivered_at": func.now(), "next_attempt_at": None}
        elif retry_at is not None:
            values |= {"next_attempt_at": retry_at}
        else:
            values |= {"status": "failed", "next_attempt_at": None}
        await self.session.execute(
            update(WebhookDeliveryRow).where(WebhookDeliveryRow.id == delivery_id).values(**values))

    async def list_deliveries(self, webhook_id: str, *, offset: int,
                              limit: int) -> list[WebhookDelivery]:
        rows = await self.session.scalars(
            select(WebhookDeliveryRow).where(WebhookDeliveryRow.webhook_id == webhook_id)
            .order_by(WebhookDeliveryRow.created_at.desc(), WebhookDeliveryRow.id)
            .offset(offset).limit(limit))
        return [_delivery(row) for row in rows]

    async def count_deliveries(self, webhook_id: str) -> int:
        return await self.session.scalar(
            select(func.count()).select_from(WebhookDeliveryRow)
            .where(WebhookDeliveryRow.webhook_id == webhook_id))


class SqlUnitOfWork:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.projects = SqlProjectRepository(session)
        self.files = SqlFileRepository(session)
        self.chunks = SqlChunkRepository(session)
        self.answers = SqlAnswerRepository(session)
        self.conversations = SqlConversationRepository(session)
        self.jobs = SqlJobRepository(session)
        self.webhooks = SqlWebhookRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


def unit_of_work_factory(
        session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AbstractAsyncContextManager[SqlUnitOfWork]]:
    """Opens a unit of work on a new session, closed (and rolled back if uncommitted) after."""

    @asynccontextmanager
    async def unit_of_work() -> AsyncIterator[SqlUnitOfWork]:
        async with session_factory() as session:
            yield SqlUnitOfWork(session)

    return unit_of_work

