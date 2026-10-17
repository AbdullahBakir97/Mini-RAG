from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from mini_rag.api.error_handlers import register_error_handlers
from mini_rag.api.routes import ask, base, data, index, projects, search
from mini_rag.core.config import Settings, get_settings
from mini_rag.core.logging_config import configure_logging
from mini_rag.embeddings.factory import create_embedder
from mini_rag.llm.factory import create_llm
from mini_rag.persistence.database import (
    create_engine,
    create_session_factory,
    stored_embedding_dimensions,
)


async def _check_embedding_dimensions(engine: AsyncEngine, settings: Settings) -> None:
    """Refuse to start when vectors would not fit the database column.

    Otherwise the mismatch would only show up at the first indexing. When
    the database cannot be asked, the app starts anyway (see /health).
    """
    stored = await stored_embedding_dimensions(engine)
    if stored is not None and stored != settings.EMBEDDING_DIMENSIONS:
        raise RuntimeError(
            f"EMBEDDING_DIMENSIONS is {settings.EMBEDDING_DIMENSIONS}, but the database stores "
            f"vectors of {stored} dimensions. Use a matching setting (and model), or change "
            f"the column with a migration.")


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
    register_error_handlers(app)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
