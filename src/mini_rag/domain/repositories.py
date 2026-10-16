"""Storage interfaces the services depend on.

Implementations live in mini_rag.persistence; tests can use in-memory
fakes. Nothing here knows about SQL.
"""

from collections.abc import Sequence
from typing import Protocol

from .models import Chunk, FileRecord, Project


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


class UnitOfWork(Protocol):
    """Repositories that share one transaction.

    Nothing is saved until ``commit``; uncommitted work is discarded.
    """

    projects: ProjectRepository
    files: FileRepository
    chunks: ChunkRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
