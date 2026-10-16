from fastapi import APIRouter, UploadFile

from mini_rag.api.dependencies import ProcessingServiceDep, UploadServiceDep
from mini_rag.api.schemas import (
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
        project_name=project_id,
        filename=file.filename or "",
        content_type=file.content_type,
        stream=file,
        declared_size=file.size,
    )
    return UploadResponse(signal=ResponseSignal.FILE_UPLOAD_SUCCESS, file_id=file_id)


@router.post(
    "/process/{project_id}",
    summary="Split an uploaded file into chunks and store them",
    description="Processing a file again replaces its previous chunks. "
                "Read the chunks with GET /api/v1/projects/{project_id}/files/{file_id}/chunks.",
    responses=error_responses(FileNotFound, UnsupportedFileType, NoTextExtracted, ProcessingFailed),
)
async def process_data(project_id: ProjectId, request: ProcessRequest,
                       processing_service: ProcessingServiceDep) -> ProcessResponse:
    chunks_count = await processing_service.process(
        project_name=project_id,
        file_key=request.file_id,
        chunk_size=request.chunk_size,
        overlap_size=request.overlap_size,
    )
    return ProcessResponse(
        signal=ResponseSignal.PROCESSING_SUCCESS,
        file_id=request.file_id,
        chunks_count=chunks_count,
    )
