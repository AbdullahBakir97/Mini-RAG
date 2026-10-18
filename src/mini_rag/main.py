import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from mini_rag.api.error_handlers import register_error_handlers
from mini_rag.api.routes import ask, base, conversations, data, index, projects, search
from mini_rag.core.config import Settings, get_settings
from mini_rag.core.logging_config import configure_logging
from mini_rag.embeddings.factory import create_embedder
from mini_rag.llm.factory import create_llm
from mini_rag.persistence.database import (
    create_engine,
    create_session_factory,
    match_embedding_dimensions,
)
from mini_rag.rerankers.factory import create_reranker

logger = logging.getLogger(__name__)


async def _check_embedding_dimensions(engine: AsyncEngine, settings: Settings) -> None:
    """Make sure vectors of EMBEDDING_DIMENSIONS fit the database column.

    The app refuses to start rather than fail at the first indexing when
    vectors of another length are stored. When the database cannot be
    asked, the app starts anyway (see /health).
    """
    wanted = settings.EMBEDDING_DIMENSIONS
    previous = await match_embedding_dimensions(engine, wanted)
    if previous is not None:
        logger.warning("No vectors were stored yet, so the vector size changed from %d to %d "
                       "dimensions to match EMBEDDING_DIMENSIONS.", previous, wanted)


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One connection pool and one client each for embeddings, the LLM and
        # reranking per app, closed cleanly on shutdown.
        engine = create_engine(settings.DATABASE_URL)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.embedder = embedder = create_embedder(settings)
        app.state.llm = llm = create_llm(settings)
        app.state.reranker = reranker = create_reranker(settings)
        try:
            await _check_embedding_dimensions(engine, settings)
            yield
        finally:
            if embedder is not None:
                await embedder.aclose()
            if llm is not None:
                await llm.aclose()
            if reranker is not None:
                await reranker.aclose()
            await engine.dispose()

    return lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION,
                  lifespan=_lifespan(settings))

    app.include_router(base.router)
    app.include_router(data.router)
    app.include_router(projects.router)
    app.include_router(index.router)
    app.include_router(search.router)
    app.include_router(ask.router)
    app.include_router(conversations.router)
    register_error_handlers(app)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
