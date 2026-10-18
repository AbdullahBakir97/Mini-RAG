"""Storage interfaces the services depend on.

Implementations live in mini_rag.persistence; tests can use in-memory
fakes. Nothing here knows about SQL.
"""

from collections.abc import Mapping, Sequence
from typing import Protocol

from .models import (
    AnswerRecord,
    Chunk,
    FileRecord,
    Project,
    ScoredChunk,
    UnembeddedChunk,
    UsageTotals,
)


class ProjectRepository(Protocol):

    async def get_by_name(self, name: str) -> Project | None: ...

    async def get_or_create(self, name: str) -> Project:
        """Return the project, creating it if needed (safe under concurrency)."""
        ...


class FileRepository(Protocol):

    async def add(self, *, project_id: int, key: str, original_name: str,
                  content_type: str, size_bytes: int) -> FileRecord: ...

    async def get_by_key(self, project_id: int, key: str) -> FileRecord | None: ...

    async def list_for_project(self, project_id: int, *, offset: int,
                               limit: int) -> list[FileRecord]:
        """Files in upload order."""
        ...

    async def count_for_project(self, project_id: int) -> int: ...


class ChunkRepository(Protocol):

    async def replace_for_file(self, file: FileRecord, chunks: Sequence[Chunk]) -> None:
        """Make ``chunks`` the file's only chunks."""
        ...

    async def list_for_file(self, file_id: int, *, offset: int, limit: int) -> list[Chunk]:
        """Chunks in index order."""
        ...

    async def count_for_file(self, file_id: int) -> int: ...

    async def count_for_project(self, project_id: int) -> int: ...

    async def list_unembedded(self, project_id: int, *, file_id: int | None,
                              limit: int) -> list[UnembeddedChunk]:
        """Chunks without an embedding, oldest first; ``file_id`` narrows to one file."""
        ...

    async def set_embeddings(self, embeddings: Mapping[int, Sequence[float]]) -> None:
        """Store vectors by chunk ID. IDs of chunks deleted meanwhile are skipped."""
        ...

    async def count_embedded_for_project(self, project_id: int) -> int: ...

    async def search(self, project_id: int, embedding: Sequence[float], *, top_k: int,
                     min_score: float | None) -> list[ScoredChunk]:
        """The project's embedded chunks most similar to ``embedding``, best first.

        At most ``top_k`` results, and none scoring below ``min_score``.
        """
        ...


class AnswerRepository(Protocol):

    async def add(self, record: AnswerRecord) -> None: ...

    async def totals_for_project(self, project_id: int) -> UsageTotals:
        """All of the project's answers added up; zeros when there are none."""
        ...


class UnitOfWork(Protocol):
    """Repositories that share one transaction.

    Nothing is saved until ``commit``; uncommitted work is discarded.
    """

    projects: ProjectRepository
    files: FileRepository
    chunks: ChunkRepository
    answers: AnswerRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
