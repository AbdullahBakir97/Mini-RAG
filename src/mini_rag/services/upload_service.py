from pathlib import Path
from typing import Protocol

import aiofiles

from mini_rag.core.errors import (
    AppError,
    FileTooLarge,
    UnsupportedFileType,
    UploadFailed,
)
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.storage.file_storage import FileStorage


class AsyncReadable(Protocol):
    """Anything uploads can be streamed from, e.g. FastAPI's UploadFile."""

    async def read(self, size: int = -1) -> bytes: ...


class UploadService:

    def __init__(self, storage: FileStorage, uow: UnitOfWork, allowed_types: list[str],
                 max_bytes: int, read_size: int):
        self.storage = storage
        self.uow = uow
        self.allowed_types = set(allowed_types)
        self.max_bytes = max_bytes
        self.read_size = read_size

    async def save(self, project_name: str, filename: str, content_type: str | None,
                   stream: AsyncReadable, declared_size: int | None = None) -> str:
        """Validate, store and record an upload, returning its file ID.

        The project is created on its first upload. The size limit is
        enforced on the bytes actually read, not only on the size the
        client declared. The file is written first and recorded second; if
        anything fails, the file is removed, so storage and database never
        disagree and a failed upload leaves nothing behind.
        """
        if content_type not in self.allowed_types:
            raise UnsupportedFileType()
        if declared_size is not None and declared_size > self.max_bytes:
            raise FileTooLarge()

        project = await self.uow.projects.get_or_create(project_name)
        file_id, path = self.storage.reserve_file(project_name, filename)
        completed = False
        try:
            size = await self._copy(stream, path)
            await self.uow.files.add(project_id=project.id, key=file_id, original_name=filename,
                                     content_type=content_type, size_bytes=size)
            await self.uow.commit()
            completed = True
        except AppError:
            raise
        except Exception as exc:
            raise UploadFailed() from exc
        finally:
            if not completed:
                path.unlink(missing_ok=True)
        return file_id

    async def _copy(self, stream: AsyncReadable, path: Path) -> int:
        """Stream into ``path`` and return the number of bytes written."""
        written = 0
        async with aiofiles.open(path, "wb") as out:
            while chunk := await stream.read(self.read_size):
                written += len(chunk)
                if written > self.max_bytes:
                    raise FileTooLarge()
                await out.write(chunk)
        return written
