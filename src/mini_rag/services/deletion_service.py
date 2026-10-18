import logging

from mini_rag.core.errors import FileNotFound, ProjectNotFound
from mini_rag.domain.repositories import UnitOfWork
from mini_rag.services.webhook_service import emit
from mini_rag.storage.file_storage import FileStorage

logger = logging.getLogger(__name__)


class DeletionService:
    """Deletes files and whole projects, everywhere at once.

    The database rows go first, with everything that depends on them
    (chunks, answers, conversations); then the files on disk. If removing a
    file from disk fails, the deletion still stands and a warning names it.
    """

    def __init__(self, uow: UnitOfWork, storage: FileStorage):
        self.uow = uow
        self.storage = storage

    async def delete_project(self, project_name: str) -> None:
        if not await self.uow.projects.delete(project_name):
            raise ProjectNotFound()
        await self.uow.commit()
        try:
            self.storage.delete_project(project_name)
        except OSError:
            logger.warning("The files of project %s could not be removed from disk.",
                           project_name, exc_info=True)

    async def delete_file(self, project_name: str, file_key: str) -> None:
        project = await self.uow.projects.get_by_name(project_name)
        if project is None:
            raise ProjectNotFound()
        if not await self.uow.files.delete(project.id, file_key):
            raise FileNotFound()
        await emit(self.uow, project, "file.deleted", {"file_id": file_key})
        await self.uow.commit()
        try:
            self.storage.delete_file(project_name, file_key)
        except OSError:
            logger.warning("The file %s of project %s could not be removed from disk.",
                           file_key, project_name, exc_info=True)
