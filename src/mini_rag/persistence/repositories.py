"""SQLAlchemy implementations of the domain repository interfaces."""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict

from sqlalchemy import bindparam, delete, func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mini_rag.domain.models import (
    AnswerRecord,
    Chunk,
    Conversation,
    ConversationMessage,
    FileRecord,
    Project,
    ScoredChunk,
    StoredCitation,
    UnembeddedChunk,
    UsageTotals,
)

from .tables import (
    AnswerRow,
    ChunkRow,
    ConversationMessageRow,
    ConversationRow,
    FileRow,
    ProjectRow,
)


def _project(row: ProjectRow) -> Project:
    return Project(id=row.id, name=row.name, created_at=row.created_at)


def _file(row: FileRow) -> FileRecord:
    return FileRecord(id=row.id, project_id=row.project_id, key=row.key,
                      original_name=row.original_name, content_type=row.content_type,
                      size_bytes=row.size_bytes, created_at=row.created_at)


def _chunk(row: ChunkRow) -> Chunk:
    return Chunk(index=row.chunk_index, text=row.text, metadata=row.meta)


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


class SqlFileRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, *, project_id: int, key: str, original_name: str,
                  content_type: str, size_bytes: int) -> FileRecord:
        row = await self.session.scalar(
            insert(FileRow)
            .values(project_id=project_id, key=key, original_name=original_name,
                    content_type=content_type, size_bytes=size_bytes)
            .returning(FileRow))
        return _file(row)

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
                     min_score: float | None) -> list[ScoredChunk]:
        # The HNSW index finds neighbours across all projects; filtering by
        # project afterwards could leave fewer than top_k. An iterative scan
        # (pgvector 0.8+) keeps searching until enough rows pass the filter.
        # It may return them slightly out of order, so the outer query sorts
        # them again. SET LOCAL lasts until the end of this transaction.
        await self.session.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))

        distance = ChunkRow.embedding.cosine_distance(list(embedding))
        nearest = (
            select(ChunkRow.id, ChunkRow.file_id, ChunkRow.chunk_index, ChunkRow.text,
                   ChunkRow.meta, distance.label("distance"))
            .where(ChunkRow.project_id == project_id, ChunkRow.embedding.is_not(None))
            .order_by(distance).limit(top_k)
            .cte("nearest").prefix_with("MATERIALIZED")
        )
        query = (
            select(nearest, FileRow.key)
            .join(FileRow, FileRow.id == nearest.c.file_id)
            .order_by(nearest.c.distance, nearest.c.id)
        )
        if min_score is not None:
            # score = 1 - cosine distance
            query = query.where(nearest.c.distance <= 1 - min_score)

        rows = await self.session.execute(query)
        return [
            ScoredChunk(file_key=row.key, score=1 - row.distance,
                        chunk=Chunk(index=row.chunk_index, text=row.text, metadata=row.meta))
            for row in rows
        ]


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


def _message(row: ConversationMessageRow) -> ConversationMessage:
    return ConversationMessage(
        role=row.role, content=row.content,
        citations=[StoredCitation(**citation) for citation in row.citations],
        prompt_version=row.prompt_version, search_question=row.search_question,
        created_at=row.created_at)


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
                           *, title: str | None = None) -> None:
        if messages:
            await self.session.execute(insert(ConversationMessageRow), [
                {"conversation_id": conversation_id, "role": message.role,
                 "content": message.content,
                 "citations": [asdict(citation) for citation in message.citations],
                 "prompt_version": message.prompt_version,
                 "search_question": message.search_question}
                for message in messages])
        values: dict = {"updated_at": func.now()}
        if title is not None:
            values["title"] = title
        await self.session.execute(
            update(ConversationRow).where(ConversationRow.id == conversation_id).values(**values))


class SqlUnitOfWork:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.projects = SqlProjectRepository(session)
        self.files = SqlFileRepository(session)
        self.chunks = SqlChunkRepository(session)
        self.answers = SqlAnswerRepository(session)
        self.conversations = SqlConversationRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
