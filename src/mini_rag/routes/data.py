from fastapi import APIRouter, Path, UploadFile
from starlette.concurrency import run_in_threadpool

from mini_rag.api.dependencies import FileStorageDep, UploadServiceDep
from mini_rag.controllers import ProcessController
from mini_rag.core.errors import (
    NoTextExtracted,
    ProcessingFailed,
    UnsupportedFileType,
)
from mini_rag.models import ResponseSignal

from .schemes import ProcessRequest

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload/{project_id}")
async def upload_data(file: UploadFile,
                      upload_service: UploadServiceDep,
                      project_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")):

    file_id = await upload_service.save(
        project_id=project_id,
        filename=file.filename or "",
        content_type=file.content_type,
        stream=file,
        declared_size=file.size,
    )

    return {
        "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
        "file_id": file_id
    }


@data_router.post("/process/{project_id}")
async def process_data(process_request: ProcessRequest,
                       storage: FileStorageDep,
                       project_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")):

    file_id = process_request.file_id
    process_controller = ProcessController(storage=storage)

    file_path = storage.get_file_path(project_id=project_id, file_id=file_id)

    if not process_controller.is_supported(file_id=file_id):
        raise UnsupportedFileType()

    try:
        # PDF parsing is CPU-bound; keep it off the event loop.
        chunks = await run_in_threadpool(
            process_controller.process_file,
            file_path=file_path,
            file_id=file_id,
            chunk_size=process_request.chunk_size,
            overlap_size=process_request.overlap_size,
        )
    except Exception as e:
        raise ProcessingFailed() from e

    if not chunks:
        raise NoTextExtracted()

    return {
        "signal": ResponseSignal.PROCESSING_SUCCESS.value,
        "file_id": file_id,
        "chunks_count": len(chunks),
        "chunks": [
            {"text": chunk.text, "metadata": chunk.metadata}
            for chunk in chunks
        ],
    }
