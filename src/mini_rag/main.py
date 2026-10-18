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
    count_embeddings,
    create_engine,
    create_session_factory,
    resize_embeddings,
    stored_embedding_dimensions,
)

logger = logging.getLogger(__name__)


async def _check_embedding_dimensions(engine: AsyncEngine, settings: Settings) -> None:
    """Make sure vectors of EMBEDDING_DIMENSIONS fit the database column.

    With no vectors stored yet, a column of another length is resized, since
    nothing is lost. Otherwise the app refuses to start rather than fail at
    the first indexing, and names the command that resizes it. When the
    database cannot be asked, the app starts anyway (see /health).
    """
    wanted = settings.EMBEDDING_DIMENSIONS
    stored = await stored_embedding_dimensions(engine)
    if stored is None or stored == wanted:
        return
    embedded = await count_embeddings(engine)
    if embedded:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS is {wanted}, but the database stores {embedded} vectors of "
            f"{stored} dimensions. Set it back to {stored}, or switch to {wanted} with "
            f"`mini-rag resize-embeddings` (with Docker: `docker compose run --rm app "
            f"mini-rag resize-embeddings`), which clears the stored vectors so the projects "
            f"can be indexed again with the new model.")
    await resize_embeddings(engine, wanted)
    logger.warning("No vectors were stored yet, so the vector size changed from %d to %d "
                   "dimensions to match EMBEDDING_DIMENSIONS.", stored, wanted)


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One connection pool, one embedding client and one LLM client per
        # app, closed cleanly on shutdown.
        engine = create_engine(settings.DATABASE_URL)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.embedder = embedder = create_embedder(settings)
        app.state.llm = llm = create_llm(settings)
        try:
            await _check_embedding_dimensions(engine, settings)
            yield
        finally:
            if embedder is not None:
                await embedder.aclose()
            if llm is not None:
                await llm.aclose()
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
