from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from mini_rag.api.error_handlers import register_error_handlers
from mini_rag.api.routes import base, data
from mini_rag.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

    app.include_router(base.router)
    app.include_router(data.router)
    register_error_handlers(app)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
