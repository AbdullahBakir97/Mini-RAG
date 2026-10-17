from fastapi import APIRouter

from mini_rag.api.dependencies import IndexingServiceDep
from mini_rag.api.schemas import IndexRequest, IndexResponse, ProjectId, error_responses
from mini_rag.core.errors import (
    EmbeddingFailed,
    EmbeddingNotConfigured,
    FileNotFound,
    ProjectNotFound,
)
from mini_rag.domain.signals import ResponseSignal

router = APIRouter(prefix="/api/v1/index", tags=["index"])


@router.post(
    "/{project_id}",
    summary="Embed a project's chunks so they can be searched",
    description="Embeds only chunks that have no embedding yet, in batches that are saved "
                "one by one: after a failure, calling again continues where it stopped, and "
                "after processing a file only its new chunks are embedded.",
    responses=error_responses(ProjectNotFound, FileNotFound, EmbeddingFailed,
                              EmbeddingNotConfigured),
)
async def index_project(project_id: ProjectId, service: IndexingServiceDep,
                        request: IndexRequest | None = None) -> IndexResponse:
    result = await service.index(project_id, file_key=request.file_id if request else None)
    return IndexResponse(signal=ResponseSignal.INDEXING_SUCCESS,
                         embedded_count=result.embedded_count, chunks_count=result.chunks_count)
