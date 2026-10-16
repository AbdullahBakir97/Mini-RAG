"""Dependency wiring: how the API builds the objects that routes use."""

from typing import Annotated

from fastapi import Depends

from mini_rag.core.config import Settings, get_settings
from mini_rag.services.upload_service import UploadService
from mini_rag.storage.file_storage import FileStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_file_storage(settings: SettingsDep) -> FileStorage:
    return FileStorage(root=settings.FILES_DIR)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def get_upload_service(storage: FileStorageDep, settings: SettingsDep) -> UploadService:
    return UploadService(
        storage=storage,
        allowed_types=settings.FILE_ALLOWED_TYPES,
        max_bytes=settings.max_upload_bytes,
        read_size=settings.FILE_DEFAULT_CHUNK_SIZE,
    )


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]
