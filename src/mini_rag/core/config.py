from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BYTES_PER_MB = 1024 * 1024


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str
    APP_VERSION: str
    OPEN_API_KEY: str
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Uploaded files are stored under FILES_DIR/<project_id>/.
    FILES_DIR: Path = Path("assets/files")
    FILE_ALLOWED_TYPES: list[str]
    FILE_MAX_SIZE: int = Field(gt=0, description="Maximum upload size in MB")
    FILE_DEFAULT_CHUNK_SIZE: int = Field(gt=0, description="Bytes read per upload chunk")

    @property
    def max_upload_bytes(self) -> int:
        return self.FILE_MAX_SIZE * BYTES_PER_MB


@lru_cache
def get_settings() -> Settings:
    return Settings()
