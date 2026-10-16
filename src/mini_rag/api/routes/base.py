from fastapi import APIRouter

from mini_rag.api.dependencies import SettingsDep
from mini_rag.api.schemas import WelcomeResponse

router = APIRouter(prefix="/api/v1", tags=["base"])


@router.get("/", summary="Service name and version")
async def welcome(settings: SettingsDep) -> WelcomeResponse:
    return WelcomeResponse(
        message="Hello All",
        app_name=settings.APP_NAME,
        app_version=settings.APP_VERSION,
    )
