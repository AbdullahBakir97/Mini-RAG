from pathlib import Path
from typing import Protocol

import aiofiles

from mini_rag.core.errors import (
    AppError,
    FileTooLarge,
    UnsupportedFileType,
    UploadFailed,
)
from mini_rag.storage.file_storage import FileStorage


class AsyncReadable(Protocol):
    """Anything uploads can be streamed from, e.g. FastAPI's UploadFile."""

    async def read(self, size: int = -1) -> bytes: ...


class UploadService:

    def __init__(self, storage: FileStorage, allowed_types: list[str],
                 max_bytes: int, read_size: int):
        self.storage = storage
        self.allowed_types = set(allowed_types)
        self.max_bytes = max_bytes
        self.read_size = read_size

    async def save(self, project_id: str, filename: str, content_type: str | None,
                   stream: AsyncReadable, declared_size: int | None = None) -> str:
        """Validate and store an upload, returning its file ID.

        The size limit is enforced on the bytes actually read, not only on
        the size the client declared. On any failure the partial file is
        removed, so a failed upload never leaves anything behind.
        """
        if content_type not in self.allowed_types:
            raise UnsupportedFileType()
        if declared_size is not None and declared_size > self.max_bytes:
            raise FileTooLarge()

        file_id, path = self.storage.reserve_file(project_id, filename)
        completed = False
        try:
            await self._copy(stream, path)
            completed = True
        except AppError:
            raise
        except Exception as exc:
            raise UploadFailed() from exc
        finally:
            if not completed:
                path.unlink(missing_ok=True)
        return file_id

    async def _copy(self, stream: AsyncReadable, path: Path) -> None:
        written = 0
        async with aiofiles.open(path, "wb") as out:
            while chunk := await stream.read(self.read_size):
                written += len(chunk)
                if written > self.max_bytes:
                    raise FileTooLarge()
                await out.write(chunk)
