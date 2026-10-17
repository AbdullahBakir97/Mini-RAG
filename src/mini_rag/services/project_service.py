from dataclasses import dataclass
from typing import Generic, TypeVar

from mini_rag.core.errors import FileNotFound, ProjectNotFound
from mini_rag.domain.models import Chunk, FileRecord, Project
from mini_rag.domain.repositories import UnitOfWork


@dataclass(frozen=True)
class ProjectSummary:
    project: Project
    files_count: int
    chunks_count: int
    embedded_chunks_count: int


T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class ProjectService:
    """Read-only queries about projects, their files and their chunks."""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def get_summary(self, project_name: str) -> ProjectSummary:
        project = await self._project(project_name)
        return ProjectSummary(
            project=project,
            files_count=await self.uow.files.count_for_project(project.id),
            chunks_count=await self.uow.chunks.count_for_project(project.id),
            embedded_chunks_count=await self.uow.chunks.count_embedded_for_project(project.id),
        )

    async def list_files(self, project_name: str, offset: int, limit: int) -> Page[FileRecord]:
        project = await self._project(project_name)
        return Page(
            items=await self.uow.files.list_for_project(project.id, offset=offset, limit=limit),
            total=await self.uow.files.count_for_project(project.id),
            offset=offset, limit=limit,
        )

    async def list_chunks(self, project_name: str, file_key: str,
                          offset: int, limit: int) -> Page[Chunk]:
        project = await self._project(project_name)
        record = await self.uow.files.get_by_key(project.id, file_key)
        if record is None:
            raise FileNotFound()
        return Page(
            items=await self.uow.chunks.list_for_file(record.id, offset=offset, limit=limit),
            total=await self.uow.chunks.count_for_file(record.id),
            offset=offset, limit=limit,
        )

    async def _project(self, name: str) -> Project:
        project = await self.uow.projects.get_by_name(name)
        if project is None:
            raise ProjectNotFound()
        return project
