"""Dependency wiring: how the API builds the objects that routes use."""

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mini_rag.core.config import Settings, get_settings
from mini_rag.core.errors import EmbeddingNotConfigured, LLMNotConfigured
from mini_rag.domain.embedder import Embedder
from mini_rag.domain.llm import LLM
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.loaders.registry import LoaderRegistry, default_loader_registry
from mini_rag.persistence.repositories import SqlUnitOfWork
from mini_rag.services.answer_service import AnswerService
from mini_rag.services.indexing_service import IndexingService
from mini_rag.services.processing_service import ProcessingService
from mini_rag.services.project_service import ProjectService
from mini_rag.services.search_service import SearchService
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


def get_embedder(request: Request) -> Embedder:
    """The app's embedder; requests that need one fail with 503 without it."""
    embedder = request.app.state.embedder
    if embedder is None:
        raise EmbeddingNotConfigured()
    return embedder


EmbedderDep = Annotated[Embedder, Depends(get_embedder)]


def get_indexing_service(uow: UnitOfWorkDep, embedder: EmbedderDep,
                         settings: SettingsDep) -> IndexingService:
    return IndexingService(uow=uow, embedder=embedder, batch_size=settings.EMBEDDING_BATCH_SIZE)


IndexingServiceDep = Annotated[IndexingService, Depends(get_indexing_service)]


def get_search_service(uow: UnitOfWorkDep, embedder: EmbedderDep) -> SearchService:
    return SearchService(uow=uow, embedder=embedder)


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]


def get_llm(request: Request) -> LLM:
    """The app's language model; requests that need one fail with 503 without it."""
    llm = request.app.state.llm
    if llm is None:
        raise LLMNotConfigured()
    return llm


LLMDep = Annotated[LLM, Depends(get_llm)]


def get_answer_service(search: SearchServiceDep, llm: LLMDep,
                       settings: SettingsDep) -> AnswerService:
    return AnswerService(search=search, llm=llm, min_score=settings.ANSWER_MIN_SCORE)


AnswerServiceDep = Annotated[AnswerService, Depends(get_answer_service)]
