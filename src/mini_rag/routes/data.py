from fastapi import APIRouter, Path, UploadFile
from starlette.concurrency import run_in_threadpool

from mini_rag.api.dependencies import ProcessingServiceDep, UploadServiceDep
from mini_rag.domain.signals import ResponseSignal

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
                       processing_service: ProcessingServiceDep,
                       project_id: str = Path(pattern=r"^[A-Za-z0-9_-]{1,64}$")):

    # PDF parsing is CPU-bound; keep it off the event loop.
    chunks = await run_in_threadpool(
        processing_service.process,
        project_id=project_id,
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
    )

    return {
        "signal": ResponseSignal.PROCESSING_SUCCESS.value,
        "file_id": process_request.file_id,
        "chunks_count": len(chunks),
        "chunks": [
            {"text": chunk.text, "metadata": chunk.metadata}
            for chunk in chunks
        ],
    }
