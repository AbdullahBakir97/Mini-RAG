from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from mini_rag.api.error_handlers import register_error_handlers
from mini_rag.routes import base, data

app = FastAPI()
app.include_router(base.base_router)
app.include_router(data.data_router)
register_error_handlers(app)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")
