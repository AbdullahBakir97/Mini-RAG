from fastapi import UploadFile

from mini_rag.core.config import Settings
from mini_rag.core.errors import FileTooLarge, UnsupportedFileType
from mini_rag.storage.file_storage import FileStorage


class DataController:

    def __init__(self, settings: Settings, storage: FileStorage):
        self.settings = settings
        self.storage = storage

    def validate_uploaded_file(self, file: UploadFile):

        if file.content_type not in self.settings.FILE_ALLOWED_TYPES:
            raise UnsupportedFileType()

        if file.size is not None and file.size > self.settings.max_upload_bytes:
            raise FileTooLarge()

    def reserve_file(self, orig_file_name: str, project_id: str):
        return self.storage.reserve_file(project_id=project_id, original_name=orig_file_name or "")
