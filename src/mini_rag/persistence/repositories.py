"""SQLAlchemy implementations of the domain repository interfaces."""

from collections.abc import Sequence

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mini_rag.domain.models import Chunk, FileRecord, Project

from .tables import ChunkRow, FileRow, ProjectRow


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


class SqlUnitOfWork:

    def __init__(self, session: AsyncSession):
        self.session = session
        self.projects = SqlProjectRepository(session)
        self.files = SqlFileRepository(session)
        self.chunks = SqlChunkRepository(session)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
