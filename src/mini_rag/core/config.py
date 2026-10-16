from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BYTES_PER_MB = 1024 * 1024

# pgvector's HNSW index supports vectors of up to 2000 dimensions.
MAX_INDEXED_DIMENSIONS = 2000


class Settings(BaseSettings):

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str
    APP_VERSION: str
    OPEN_API_KEY: str
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    DATABASE_URL: str = Field(
        description="PostgreSQL URL for SQLAlchemy, e.g. postgresql+asyncpg://user:password@host:5432/db",
    )

    # Uploaded files are stored under FILES_DIR/<project_id>/.
    FILES_DIR: Path = Path("assets/files")
    FILE_ALLOWED_TYPES: list[str]
    FILE_MAX_SIZE: int = Field(gt=0, description="Maximum upload size in MB")
    FILE_DEFAULT_CHUNK_SIZE: int = Field(gt=0, description="Bytes read per upload chunk")

    # Embeddings come from the OpenAI API, or from any OpenAI-compatible
    # server (such as Ollama) when EMBEDDING_BASE_URL is set.
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = Field(
        default=1536, gt=0, le=MAX_INDEXED_DIMENSIONS,
        description="Vector length; must match the chunks.embedding column")
    EMBEDDING_BATCH_SIZE: int = Field(default=64, gt=0, le=2048,
                                      description="Texts sent per embedding request")

    @field_validator("DATABASE_URL")
    @classmethod
    def check_async_postgres_url(cls, url: str) -> str:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with postgresql+asyncpg://")
        return url

    @field_validator("EMBEDDING_BASE_URL")
    @classmethod
    def empty_base_url_means_default(cls, url: str | None) -> str | None:
        return url or None

    @property
    def embeddings_configured(self) -> bool:
        """Whether there is an API key, or a server that may not need one."""
        return bool(self.OPEN_API_KEY or self.EMBEDDING_BASE_URL)

    @property
    def max_upload_bytes(self) -> int:
        return self.FILE_MAX_SIZE * BYTES_PER_MB


@lru_cache
def get_settings() -> Settings:
    return Settings()
