from fastapi import APIRouter

from mini_rag.api.dependencies import AnswerServiceDep
from mini_rag.api.schemas import (
    AskRequest,
    AskResponse,
    CitationResponse,
    ProjectId,
    error_responses,
)
from mini_rag.core.errors import (
    EmbeddingFailed,
    EmbeddingNotConfigured,
    LLMFailed,
    LLMNotConfigured,
    ProjectNotFound,
)
from mini_rag.domain.signals import ResponseSignal

router = APIRouter(prefix="/api/v1/ask", tags=["ask"])


@router.post(
    "/{project_id}",
    summary="Answer a question from the project's documents",
    description="Finds the indexed chunks that best match the question and has a language model "
                "answer from them, citing each source as [n]. Signal `no_answer`, with `answer` "
                "null, means the documents do not answer the question.",
    responses=error_responses(ProjectNotFound, EmbeddingFailed, LLMFailed,
                              EmbeddingNotConfigured, LLMNotConfigured),
)
async def ask_project(project_id: ProjectId, request: AskRequest,
                      service: AnswerServiceDep) -> AskResponse:
    answer = await service.ask(project_id, request.question, top_k=request.top_k,
                               min_score=request.min_score)
    return AskResponse(
        signal=ResponseSignal.ANSWER_SUCCESS if answer.text is not None else ResponseSignal.NO_ANSWER,
        answer=answer.text,
        citations=[CitationResponse(number=citation.number, file_id=citation.source.file_key,
                                    chunk_index=citation.source.chunk.index,
                                    page=citation.source.chunk.metadata.get("page"),
                                    score=citation.source.score, text=citation.source.chunk.text)
                   for citation in answer.citations],
        prompt_version=answer.prompt_version)
