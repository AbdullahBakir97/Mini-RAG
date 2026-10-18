import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import aiofiles

from mini_rag.core.errors import (
    AppError,
    FileTooLarge,
    UnsupportedFileType,
    UploadFailed,
)
from mini_rag.domain.file_types import content_type_for
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.services.webhook_service import emit
from mini_rag.storage.file_storage import FileStorage


class AsyncReadable(Protocol):
    """Anything uploads can be streamed from, e.g. FastAPI's UploadFile."""

    async def read(self, size: int = -1) -> bytes: ...


@dataclass(frozen=True)
class Upload:
    """``file_id`` of the stored file; ``duplicate`` when the project already had its content."""

    file_id: str
    duplicate: bool = False


class UploadService:

    def __init__(self, storage: FileStorage, uow: UnitOfWork, allowed_types: list[str],
                 max_bytes: int, read_size: int):
        self.storage = storage
        self.uow = uow
        self.allowed_types = set(allowed_types)
        self.max_bytes = max_bytes
        self.read_size = read_size

    async def save(self, project_name: str, filename: str, content_type: str | None,
                   stream: AsyncReadable, declared_size: int | None = None) -> Upload:
        """Validate, store and record an upload.

        The project is created on its first upload. The size limit is
        enforced on the bytes actually read, not only on the size the
        client declared. The file is written first and recorded second; if
        anything fails, the file is removed, so storage and database never
        disagree and a failed upload leaves nothing behind. Content the
        project already has is not stored again: the existing file is
        returned, marked as a duplicate. A missing or generic content type
        is taken from the file's extension.
        """
        content_type = content_type_for(filename, content_type)
        if content_type not in self.allowed_types:
            raise UnsupportedFileType()
        if declared_size is not None and declared_size > self.max_bytes:
            raise FileTooLarge()

        project = await self.uow.projects.get_or_create(project_name)
        file_id, path = self.storage.reserve_file(project.folder, filename)
        completed = False
        try:
            size, digest = await self._copy(stream, path)
            existing = await self.uow.files.get_by_content(project.id, digest)
            record = existing is None and await self.uow.files.add(
                project_id=project.id, key=file_id, original_name=filename,
                content_type=content_type, size_bytes=size, content_sha256=digest)
            if record:
                await emit(self.uow, project, "file.uploaded", {
                    "file_id": record.key, "original_name": record.original_name,
                    "content_type": record.content_type, "size_bytes": record.size_bytes})
                await self.uow.commit()
                completed = True
                return Upload(file_id=file_id)
            # Already there, or recorded by another upload of it a moment ago.
            existing = existing or await self.uow.files.get_by_content(project.id, digest)
            await self.uow.commit()
            return Upload(file_id=existing.key, duplicate=True)
        except AppError:
            raise
        except Exception as exc:
            raise UploadFailed() from exc
        finally:
            if not completed:
                path.unlink(missing_ok=True)

    async def _copy(self, stream: AsyncReadable, path: Path) -> tuple[int, str]:
        """Stream into ``path``; returns the number of bytes written and their SHA-256."""
        written = 0
        digest = hashlib.sha256()
        async with aiofiles.open(path, "wb") as out:
            while chunk := await stream.read(self.read_size):
                written += len(chunk)
                if written > self.max_bytes:
                    raise FileTooLarge()
                digest.update(chunk)
                await out.write(chunk)
        return written, digest.hexdigest()
