from dataclasses import dataclass

from mini_rag.core.errors import ConversationNotFound, ProjectNotFound
from mini_rag.domain.models import Conversation, ConversationMessage, Project
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.services.project_service import Page


@dataclass(frozen=True)
class ConversationWithMessages:
    conversation: Conversation
    messages: list[ConversationMessage]


class ConversationService:
    """Starts, lists, reads and deletes a project's conversations.

    Questions are asked in a conversation through the AnswerService.
    """

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def create(self, project_name: str, title: str | None = None) -> Conversation:
        project = await self._project(project_name)
        conversation = await self.uow.conversations.create(project.id, title)
        await self.uow.commit()
        return conversation

    async def list(self, project_name: str, offset: int, limit: int) -> Page[Conversation]:
        project = await self._project(project_name)
        return Page(
            items=await self.uow.conversations.list_for_project(project.id, offset=offset,
                                                                limit=limit),
            total=await self.uow.conversations.count_for_project(project.id),
            offset=offset, limit=limit,
        )

    async def get(self, project_name: str, conversation_id: str) -> ConversationWithMessages:
        project = await self._project(project_name)
        conversation = await self.uow.conversations.get(project.id, conversation_id)
        if conversation is None:
            raise ConversationNotFound()
        return ConversationWithMessages(
            conversation=conversation,
            messages=await self.uow.conversations.messages(conversation.id))

    async def delete(self, project_name: str, conversation_id: str) -> None:
        project = await self._project(project_name)
        if not await self.uow.conversations.delete(project.id, conversation_id):
            raise ConversationNotFound()
        await self.uow.commit()

    async def _project(self, name: str) -> Project:
        project = await self.uow.projects.get_by_name(name)
        if project is None:
            raise ProjectNotFound()
        return project
