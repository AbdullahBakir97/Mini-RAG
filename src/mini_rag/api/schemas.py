"""Request and response models, and the shared ID types used by routes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import Path, Query
from pydantic import BaseModel, Field, model_validator

from mini_rag.core.errors import AppError
from mini_rag.domain.signals import ResponseSignal

ProjectId = Annotated[str, Path(
    pattern=r"^[A-Za-z0-9_-]{1,64}$",
    description="Project name: letters, digits, '_' and '-' (1-64 characters).",
)]

FILE_ID_PATTERN = r"^[\w.]+$"
FILE_ID_DESCRIPTION = "The file_id returned by the upload endpoint."

FileId = Annotated[str, Field(pattern=FILE_ID_PATTERN, max_length=255,
                              description=FILE_ID_DESCRIPTION)]
FileIdPath = Annotated[str, Path(pattern=FILE_ID_PATTERN, max_length=255,
                                 description=FILE_ID_DESCRIPTION)]


@dataclass
class Pagination:
    """Shared offset/limit query parameters for list endpoints."""

    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0
    limit: Annotated[int, Query(ge=1, le=100, description="Items to return (1-100).")] = 20


class ErrorResponse(BaseModel):
    signal: ResponseSignal


def error_responses(*errors: type[AppError]) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entries for the errors a route can raise, grouped by status."""
    responses: dict[int | str, dict[str, Any]] = {}
    for error in errors:
        entry = responses.setdefault(int(error.status_code), {"model": ErrorResponse, "signals": []})
        entry["signals"].append(f"`{error.signal.value}`")
    return {
        status: {"model": entry["model"], "description": "Signal: " + ", ".join(entry["signals"])}
        for status, entry in responses.items()
    }


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


class WelcomeResponse(BaseModel):
    message: str
    app_name: str
    app_version: str


class UploadResponse(BaseModel):
    signal: ResponseSignal
    file_id: str


class ProcessRequest(BaseModel):
    file_id: FileId
    chunk_size: int = Field(default=1000, gt=0, le=100_000,
                            description="Maximum chunk length in characters, overlap included.")
    overlap_size: int = Field(default=200, ge=0,
                              description="Characters of preceding text repeated at the start of each chunk.")

    @model_validator(mode="after")
    def check_overlap_smaller_than_chunk(self):
        if self.overlap_size >= self.chunk_size:
            raise ValueError("overlap_size must be smaller than chunk_size")
        return self


class ProcessResponse(BaseModel):
    signal: ResponseSignal
    file_id: str
    chunks_count: int


class IndexRequest(BaseModel):
    file_id: FileId | None = Field(default=None,
                                   description="Index only this file; omit for the whole project.")


class IndexResponse(BaseModel):
    signal: ResponseSignal
    embedded_count: int = Field(description="Chunks embedded by this request.")
    chunks_count: int = Field(description="All chunks of the project, or of the file.")


class ProjectResponse(BaseModel):
    name: str
    created_at: datetime
    files_count: int
    chunks_count: int


class FileResponse(BaseModel):
    file_id: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class FileListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[FileResponse]


class ChunkResponse(BaseModel):
    chunk_index: int
    text: str
    metadata: dict[str, Any]


class ChunkListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ChunkResponse]
