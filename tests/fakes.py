"""In-memory implementations of the domain repository interfaces.

They let service tests run without a database. Changes are visible
immediately (there are no real transactions); tests check ``commits``
to verify the service committed its work.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count

from mini_rag.domain.models import (
    Chunk,
    FileRecord,
    Project,
    ScoredChunk,
    UnembeddedChunk,
)


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
