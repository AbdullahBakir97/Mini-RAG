"""Request and response models, and the shared ID types used by routes."""

from typing import Annotated, Any

from fastapi import Path
from pydantic import BaseModel, Field, model_validator

from mini_rag.core.errors import AppError
from mini_rag.domain.signals import ResponseSignal

ProjectId = Annotated[str, Path(
    pattern=r"^[A-Za-z0-9_-]{1,64}$",
    description="Project name: letters, digits, '_' and '-' (1-64 characters).",
)]

FileId = Annotated[str, Field(
    pattern=r"^[\w.]+$",
    max_length=255,
    description="The file_id returned by the upload endpoint.",
)]


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
