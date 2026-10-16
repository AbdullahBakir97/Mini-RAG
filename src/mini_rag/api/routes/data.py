from fastapi import APIRouter, UploadFile
from starlette.concurrency import run_in_threadpool

from mini_rag.api.dependencies import ProcessingServiceDep, UploadServiceDep
from mini_rag.api.schemas import (
    ChunkResponse,
    ProcessRequest,
    ProcessResponse,
    ProjectId,
    UploadResponse,
    error_responses,
)
from mini_rag.core.errors import (
    FileNotFound,
    FileTooLarge,
    NoTextExtracted,
    ProcessingFailed,
    UnsupportedFileType,
    UploadFailed,
)
from mini_rag.domain.signals import ResponseSignal

router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.post(
    "/upload/{project_id}",
    summary="Upload a file into a project",
    responses=error_responses(UnsupportedFileType, FileTooLarge, UploadFailed),
)
async def upload_data(project_id: ProjectId, file: UploadFile,
                      upload_service: UploadServiceDep) -> UploadResponse:
    file_id = await upload_service.save(
        project_id=project_id,
        filename=file.filename or "",
        content_type=file.content_type,
        stream=file,
        declared_size=file.size,
    )
    return UploadResponse(signal=ResponseSignal.FILE_UPLOAD_SUCCESS, file_id=file_id)


@router.post(
    "/process/{project_id}",
    summary="Split an uploaded file into text chunks",
    responses=error_responses(FileNotFound, UnsupportedFileType, NoTextExtracted, ProcessingFailed),
)
async def process_data(project_id: ProjectId, request: ProcessRequest,
                       processing_service: ProcessingServiceDep) -> ProcessResponse:
    # PDF parsing is CPU-bound; keep it off the event loop.
    chunks = await run_in_threadpool(
        processing_service.process,
        project_id=project_id,
        file_id=request.file_id,
        chunk_size=request.chunk_size,
        overlap_size=request.overlap_size,
    )
    return ProcessResponse(
        signal=ResponseSignal.PROCESSING_SUCCESS,
        file_id=request.file_id,
        chunks_count=len(chunks),
        chunks=[ChunkResponse(text=chunk.text,
                              metadata={**chunk.metadata, "chunk_index": chunk.index})
                for chunk in chunks],
    )
