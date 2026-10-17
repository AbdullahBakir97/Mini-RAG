"""Dependency wiring: how the API builds the objects that routes use."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from mini_rag.core.config import Settings, get_settings
from mini_rag.loaders.registry import LoaderRegistry, default_loader_registry
from mini_rag.services.processing_service import ProcessingService
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


@lru_cache
def get_loader_registry() -> LoaderRegistry:
    return default_loader_registry()


LoaderRegistryDep = Annotated[LoaderRegistry, Depends(get_loader_registry)]


def get_processing_service(storage: FileStorageDep, loaders: LoaderRegistryDep) -> ProcessingService:
    return ProcessingService(storage=storage, loaders=loaders)


ProcessingServiceDep = Annotated[ProcessingService, Depends(get_processing_service)]
