"""Dependency wiring: how the API builds the objects that routes use."""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mini_rag.core.config import Settings, get_settings
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.loaders.registry import LoaderRegistry, default_loader_registry
from mini_rag.persistence.repositories import SqlUnitOfWork
from mini_rag.services.processing_service import ProcessingService
from mini_rag.services.project_service import ProjectService
from mini_rag.services.upload_service import UploadService
from mini_rag.storage.file_storage import FileStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.engine


EngineDep = Annotated[AsyncEngine, Depends(get_engine)]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


async def get_session(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    """One session (and transaction) per request; uncommitted work is rolled back."""
    async with factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_unit_of_work(session: SessionDep) -> UnitOfWork:
    return SqlUnitOfWork(session)


UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]


def get_file_storage(settings: SettingsDep) -> FileStorage:
    return FileStorage(root=settings.FILES_DIR)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def get_upload_service(storage: FileStorageDep, uow: UnitOfWorkDep,
                       settings: SettingsDep) -> UploadService:
    return UploadService(
        storage=storage,
        uow=uow,
        allowed_types=settings.FILE_ALLOWED_TYPES,
        max_bytes=settings.max_upload_bytes,
        read_size=settings.FILE_DEFAULT_CHUNK_SIZE,
    )


UploadServiceDep = Annotated[UploadService, Depends(get_upload_service)]


@lru_cache
def get_loader_registry() -> LoaderRegistry:
    return default_loader_registry()


LoaderRegistryDep = Annotated[LoaderRegistry, Depends(get_loader_registry)]


def get_processing_service(storage: FileStorageDep, loaders: LoaderRegistryDep,
                           uow: UnitOfWorkDep) -> ProcessingService:
    return ProcessingService(storage=storage, loaders=loaders, uow=uow)


ProcessingServiceDep = Annotated[ProcessingService, Depends(get_processing_service)]


def get_project_service(uow: UnitOfWorkDep) -> ProjectService:
    return ProjectService(uow=uow)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
