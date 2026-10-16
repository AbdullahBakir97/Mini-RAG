"""Dependency wiring: how the API builds the objects that routes use."""

from typing import Annotated

from fastapi import Depends

from mini_rag.core.config import Settings, get_settings
from mini_rag.storage.file_storage import FileStorage

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_file_storage(settings: SettingsDep) -> FileStorage:
    return FileStorage(root=settings.FILES_DIR)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]
