"""In-memory implementations of the domain repository interfaces.

They let service tests run without a database. Changes are visible
immediately (there are no real transactions); tests check ``commits``
to verify the service committed its work.
"""

import math
import re
import zlib
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count

from mini_rag.core.errors import EmbeddingFailed, LLMFailed
from mini_rag.domain.llm import Message
from mini_rag.domain.models import (
    Chunk,
    FileRecord,
    Project,
    ScoredChunk,
    UnembeddedChunk,
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


class FakeUnitOfWork:

    def __init__(self):
        self.projects = FakeProjects()
        self.files = FakeFiles()
        self.chunks = FakeChunks()
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


class FakeLLM:
    """Replies with ``reply``, or raises LLMFailed when ``fail`` is set.

    Streams the reply in pieces of ``piece_size`` characters; ``fail_after``
    makes a stream raise LLMFailed after that many pieces. ``calls`` records
    the messages of every request.
    """

    model = "fake-llm"

    def __init__(self, reply: str = "A fake answer.", fail: bool = False, piece_size: int = 4,
                 fail_after: int | None = None):
        self.reply = reply
        self.fail = fail
        self.piece_size = piece_size
        self.fail_after = fail_after
        self.calls: list[list[Message]] = []

    async def complete(self, messages: Sequence[Message]) -> str:
        self.calls.append(list(messages))
        if self.fail:
            raise LLMFailed("fake failure")
        return self.reply

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        self.calls.append(list(messages))
        if self.fail:
            raise LLMFailed("fake failure")
        for sent, start in enumerate(range(0, len(self.reply), self.piece_size)):
            if sent == self.fail_after:
                raise LLMFailed("fake failure mid-stream")
            yield self.reply[start:start + self.piece_size]
