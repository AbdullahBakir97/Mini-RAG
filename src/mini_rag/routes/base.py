from fastapi import APIRouter

from mini_rag.api.dependencies import SettingsDep

base_router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)

@base_router.get("/")
async def welcome(app_settings: SettingsDep):

    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION

    return{
        "message": "Hello All",
        "app_name": app_name,
        "app_version": app_version,
    }
