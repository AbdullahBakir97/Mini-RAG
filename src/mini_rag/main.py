from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from mini_rag.api.error_handlers import register_error_handlers
from mini_rag.api.routes import base, data, projects
from mini_rag.core.config import Settings, get_settings
from mini_rag.core.logging_config import configure_logging
from mini_rag.persistence.database import create_engine, create_session_factory


def _lifespan(settings: Settings) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One connection pool per app, closed cleanly on shutdown.
        engine = create_engine(settings.DATABASE_URL)
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
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
    register_error_handlers(app)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
