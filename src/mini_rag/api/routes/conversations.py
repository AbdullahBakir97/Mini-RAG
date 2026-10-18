from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from mini_rag.api.dependencies import ConversationServiceDep
from mini_rag.api.schemas import (
    CitationResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationIdPath,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    Pagination,
    ProjectId,
    error_responses,
)
from mini_rag.core.errors import ConversationNotFound, ProjectNotFound
from mini_rag.domain.models import Conversation, ConversationMessage

router = APIRouter(prefix="/api/v1/projects", tags=["conversations"])

PaginationDep = Annotated[Pagination, Depends()]


def _conversation(conversation: Conversation) -> dict:
    return {"id": conversation.id, "title": conversation.title,
            "created_at": conversation.created_at, "updated_at": conversation.updated_at}


def _message(message: ConversationMessage) -> MessageResponse:
    return MessageResponse(
        role=message.role, content=message.content,
        citations=[CitationResponse(number=c.number, file_id=c.file_key, chunk_index=c.chunk_index,
                                    page=c.page, score=c.score, text=c.text)
                   for c in message.citations],
        prompt_version=message.prompt_version, search_question=message.search_question,
        created_at=message.created_at)


@router.post("/{project_id}/conversations", status_code=status.HTTP_201_CREATED,
             summary="Start a conversation",
             description="Ask in it with POST /api/v1/ask/{project_id} and its `conversation_id`.",
             responses=error_responses(ProjectNotFound))
async def create_conversation(project_id: ProjectId, service: ConversationServiceDep,
                              request: ConversationCreateRequest | None = None,
                              ) -> ConversationResponse:
    conversation = await service.create(project_id, request.title if request else None)
    return ConversationResponse(**_conversation(conversation))


@router.get("/{project_id}/conversations", summary="List conversations, most recent first",
            responses=error_responses(ProjectNotFound))
async def list_conversations(project_id: ProjectId, page: PaginationDep,
                             service: ConversationServiceDep) -> ConversationListResponse:
    result = await service.list(project_id, offset=page.offset, limit=page.limit)
    return ConversationListResponse(
        total=result.total, offset=result.offset, limit=result.limit,
        items=[ConversationResponse(**_conversation(c)) for c in result.items])


@router.get("/{project_id}/conversations/{conversation_id}",
            summary="A conversation with its questions and answers",
            responses=error_responses(ProjectNotFound, ConversationNotFound))
async def get_conversation(project_id: ProjectId, conversation_id: ConversationIdPath,
                           service: ConversationServiceDep) -> ConversationDetailResponse:
    found = await service.get(project_id, str(conversation_id))
    return ConversationDetailResponse(**_conversation(found.conversation),
                                      messages=[_message(m) for m in found.messages])


@router.delete("/{project_id}/conversations/{conversation_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a conversation and its messages",
               responses=error_responses(ProjectNotFound, ConversationNotFound))
async def delete_conversation(project_id: ProjectId, conversation_id: ConversationIdPath,
                              service: ConversationServiceDep) -> Response:
    await service.delete(project_id, str(conversation_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
