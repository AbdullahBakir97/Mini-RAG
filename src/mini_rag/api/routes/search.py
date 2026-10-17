from fastapi import APIRouter

from mini_rag.api.dependencies import SearchServiceDep
from mini_rag.api.schemas import (
    ProjectId,
    SearchRequest,
    SearchResponse,
    SearchResult,
    error_responses,
)
from mini_rag.core.errors import (
    EmbeddingFailed,
    EmbeddingNotConfigured,
    ProjectNotFound,
)
from mini_rag.domain.signals import ResponseSignal

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post(
    "/{project_id}",
    summary="Find the chunks that best match a question",
    description="Searches the project's indexed chunks (see POST /api/v1/index/{project_id}) "
                "by meaning, best match first. Chunks that are not indexed yet are not found.",
    responses=error_responses(ProjectNotFound, EmbeddingFailed, EmbeddingNotConfigured),
)
async def search_project(project_id: ProjectId, request: SearchRequest,
                         service: SearchServiceDep) -> SearchResponse:
    hits = await service.search(project_id, request.query, top_k=request.top_k,
                                min_score=request.min_score)
    return SearchResponse(
        signal=ResponseSignal.SEARCH_SUCCESS,
        results=[SearchResult(file_id=hit.file_key, chunk_index=hit.chunk.index, score=hit.score,
                              text=hit.chunk.text, metadata=hit.chunk.metadata)
                 for hit in hits])
