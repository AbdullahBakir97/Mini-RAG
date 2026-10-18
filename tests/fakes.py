"""In-memory implementations of the domain repository interfaces.

They let service tests run without a database. Changes are visible
immediately (there are no real transactions); tests check ``commits``
to verify the service committed its work.
"""

import math
import re
import uuid
import zlib
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from itertools import count

from mini_rag.core.errors import EmbeddingFailed, LLMFailed
from mini_rag.domain.llm import Completion, Message, TokenUsage
from mini_rag.domain.models import (
    AnswerRecord,
    Chunk,
    Conversation,
    ConversationMessage,
    FileRecord,
    Project,
    ScoredChunk,
    UnembeddedChunk,
    UsageTotals,
)
from mini_rag.persistence.tables import EMBEDDING_DIMENSIONS


class FakeProjects:

    def __init__(self):
        self.by_name: dict[str, Project] = {}
        self._ids = count(1)

    async def get_by_name(self, name: str) -> Project | None:
        return self.by_name.get(name)

    async def get_or_create(self, name: str) -> Project:
        if name not in self.by_name:
            self.by_name[name] = Project(id=next(self._ids), name=name, created_at=datetime.now(UTC))
        return self.by_name[name]

    async def list_all(self, *, offset: int, limit: int) -> list[Project]:
        return [self.by_name[name] for name in sorted(self.by_name)][offset:offset + limit]

    async def count(self) -> int:
        return len(self.by_name)

    async def delete(self, name: str) -> bool:
        return self.by_name.pop(name, None) is not None


class FakeFiles:

    def __init__(self):
        self.records: list[FileRecord] = []
        self._ids = count(1)
        self.fail_with: Exception | None = None

    async def add(self, *, project_id, key, original_name, content_type, size_bytes) -> FileRecord:
        if self.fail_with:
            raise self.fail_with
        record = FileRecord(id=next(self._ids), project_id=project_id, key=key,
                            original_name=original_name, content_type=content_type,
                            size_bytes=size_bytes, created_at=datetime.now(UTC))
        self.records.append(record)
        return record

    async def get_by_key(self, project_id: int, key: str) -> FileRecord | None:
        return next((r for r in self.records if r.project_id == project_id and r.key == key), None)

    async def list_for_project(self, project_id: int, *, offset: int, limit: int) -> list[FileRecord]:
        return [r for r in self.records if r.project_id == project_id][offset:offset + limit]

    async def count_for_project(self, project_id: int) -> int:
        return sum(r.project_id == project_id for r in self.records)


@dataclass
class StoredChunk:
    """One row of the fake chunks table."""

    id: int
    file: FileRecord
    chunk: Chunk
    embedding: list[float] | None = None


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (math.hypot(*a) * math.hypot(*b))


class FakeChunks:

    def __init__(self):
        self.rows: list[StoredChunk] = []
        self._ids = count(1)

    async def replace_for_file(self, file: FileRecord, chunks: Sequence[Chunk]) -> None:
        self.rows = [row for row in self.rows if row.file.id != file.id]
        self.rows += [StoredChunk(id=next(self._ids), file=file, chunk=chunk) for chunk in chunks]

    async def list_for_file(self, file_id: int, *, offset: int, limit: int) -> list[Chunk]:
        chunks = sorted((row.chunk for row in self.rows if row.file.id == file_id),
                        key=lambda c: c.index)
        return chunks[offset:offset + limit]

    async def count_for_file(self, file_id: int) -> int:
        return sum(row.file.id == file_id for row in self.rows)

    async def count_for_project(self, project_id: int) -> int:
        return sum(row.file.project_id == project_id for row in self.rows)

    async def list_unembedded(self, project_id: int, *, file_id: int | None,
                              limit: int) -> list[UnembeddedChunk]:
        pending = [row for row in self.rows
                   if row.file.project_id == project_id and row.embedding is None
                   and file_id in (None, row.file.id)]
        return [UnembeddedChunk(id=row.id, text=row.chunk.text) for row in pending[:limit]]

    async def set_embeddings(self, embeddings: Mapping[int, Sequence[float]]) -> None:
        for row in self.rows:
            if row.id in embeddings:
                row.embedding = list(embeddings[row.id])

    async def count_embedded_for_project(self, project_id: int) -> int:
        return sum(row.file.project_id == project_id and row.embedding is not None
                   for row in self.rows)

    async def search(self, project_id: int, embedding: Sequence[float], *, top_k: int,
                     min_score: float | None) -> list[ScoredChunk]:
        hits = [ScoredChunk(file_key=row.file.key, chunk=row.chunk,
                            score=cosine_similarity(row.embedding, embedding))
                for row in self.rows
                if row.file.project_id == project_id and row.embedding is not None]
        hits.sort(key=lambda hit: -hit.score)
        return [hit for hit in hits[:top_k] if min_score is None or hit.score >= min_score]


class FakeAnswers:

    def __init__(self):
        self.records: list[AnswerRecord] = []

    async def add(self, record: AnswerRecord) -> None:
        self.records.append(record)

    async def totals_for_project(self, project_id: int) -> UsageTotals:
        records = [r for r in self.records if r.project_id == project_id]
        return UsageTotals(
            answers=len(records), answered=sum(r.answered for r in records),
            input_tokens=sum(r.input_tokens or 0 for r in records),
            output_tokens=sum(r.output_tokens or 0 for r in records),
            cost_usd=sum(r.cost_usd or 0 for r in records),
            unpriced_answers=sum(r.model is not None and r.cost_usd is None for r in records))


class FakeConversations:

    def __init__(self):
        self.by_id: dict[str, Conversation] = {}
        self.stored: dict[str, list[ConversationMessage]] = {}

    async def create(self, project_id: int, title: str | None) -> Conversation:
        now = datetime.now(UTC)
        conversation = Conversation(id=str(uuid.uuid4()), project_id=project_id, title=title,
                                    created_at=now, updated_at=now)
        self.by_id[conversation.id] = conversation
        self.stored[conversation.id] = []
        return conversation

    async def get(self, project_id: int, conversation_id: str) -> Conversation | None:
        conversation = self.by_id.get(conversation_id)
        return conversation if conversation and conversation.project_id == project_id else None

    async def list_for_project(self, project_id: int, *, offset: int,
                               limit: int) -> list[Conversation]:
        mine = [c for c in self.by_id.values() if c.project_id == project_id]
        mine.sort(key=lambda c: c.updated_at, reverse=True)
        return mine[offset:offset + limit]

    async def count_for_project(self, project_id: int) -> int:
        return sum(c.project_id == project_id for c in self.by_id.values())

    async def delete(self, project_id: int, conversation_id: str) -> bool:
        if await self.get(project_id, conversation_id) is None:
            return False
        del self.by_id[conversation_id]
        del self.stored[conversation_id]
        return True

    async def messages(self, conversation_id: str, *,
                       last: int | None = None) -> list[ConversationMessage]:
        messages = self.stored.get(conversation_id, [])
        return list(messages[-last:] if last else messages)

    async def add_messages(self, conversation_id: str, messages: Sequence[ConversationMessage],
                           *, title: str | None = None) -> None:
        self.stored[conversation_id].extend(messages)
        conversation = self.by_id[conversation_id]
        self.by_id[conversation_id] = replace(
            conversation, updated_at=datetime.now(UTC),
            title=title if title is not None else conversation.title)


class FakeUnitOfWork:

    def __init__(self):
        self.projects = FakeProjects()
        self.files = FakeFiles()
        self.chunks = FakeChunks()
        self.answers = FakeAnswers()
        self.conversations = FakeConversations()
        self.commits = 0
        self.fail_commit_with: Exception | None = None

    async def commit(self) -> None:
        if self.fail_commit_with:
            raise self.fail_commit_with
        self.commits += 1

    async def rollback(self) -> None:
        pass


class FakeEmbedder:
    """Deterministic bag-of-words vectors, so texts sharing words are similar.

    Each word adds 1 to a dimension chosen by a stable hash of the word.
    ``fail_on_call`` makes that call (1-based) raise EmbeddingFailed.
    """

    model = "fake-embedder"

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS, fail_on_call: int | None = None):
        self.dimensions = dimensions
        self.fail_on_call = fail_on_call
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if len(self.calls) == self.fail_on_call:
            raise EmbeddingFailed("fake failure")
        return [self.vector(text) for text in texts]

    def vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        vector[0] = 0.01  # never all zeros, which has no direction
        for word in re.findall(r"\w+", text.lower()):
            vector[1 + zlib.crc32(word.encode()) % (self.dimensions - 1)] += 1.0
        return vector


FAKE_USAGE = TokenUsage(input_tokens=1200, output_tokens=40)


class FakeLLM:
    """Replies with ``reply`` and reports ``usage``, or raises LLMFailed when ``fail`` is set.

    Streams the reply in pieces of ``piece_size`` characters, then the usage
    unless it is None; ``fail_after`` makes a stream raise LLMFailed after
    that many pieces. ``calls`` records the messages of every request.
    """

    model = "fake-llm"

    def __init__(self, reply: str = "A fake answer.", fail: bool = False, piece_size: int = 4,
                 fail_after: int | None = None, usage: TokenUsage | None = FAKE_USAGE,
                 replies: Sequence[str] = ()):
        self.reply = reply
        # Replies for the first requests, in order; ``reply`` for the rest.
        self.replies = list(replies)
        self.fail = fail
        self.piece_size = piece_size
        self.fail_after = fail_after
        self.usage = usage
        self.calls: list[list[Message]] = []

    async def complete(self, messages: Sequence[Message]) -> Completion:
        self.calls.append(list(messages))
        if self.fail:
            raise LLMFailed("fake failure")
        return Completion(text=self._next_reply(), usage=self.usage)

    def _next_reply(self) -> str:
        return self.replies.pop(0) if self.replies else self.reply

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str | TokenUsage]:
        self.calls.append(list(messages))
        if self.fail:
            raise LLMFailed("fake failure")
        reply = self._next_reply()
        for sent, start in enumerate(range(0, len(reply), self.piece_size)):
            if sent == self.fail_after:
                raise LLMFailed("fake failure mid-stream")
            yield reply[start:start + self.piece_size]
        if self.usage is not None:
            yield self.usage
