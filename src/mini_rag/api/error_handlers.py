import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mini_rag.core.errors import AppError

logger = logging.getLogger(__name__)


async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error("%s %s failed: %s", request.method, request.url.path, exc,
                     exc_info=exc.__cause__ or exc)
    return JSONResponse(status_code=exc.status_code, content={"signal": exc.signal.value})


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
