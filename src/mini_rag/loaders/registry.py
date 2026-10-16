from collections.abc import Mapping
from pathlib import PurePath

from mini_rag.core.errors import UnsupportedFileType

from .base import DocumentLoader
from .pdf_loader import PdfLoader
from .text_loader import TextLoader


class LoaderRegistry:
    """Chooses a document loader by file extension (case-insensitive).

    Supporting a new file type means registering a loader here; nothing
    that uses the registry has to change.
    """

    def __init__(self, loaders: Mapping[str, DocumentLoader]):
        self._loaders = {extension.lower(): loader for extension, loader in loaders.items()}

    @property
    def extensions(self) -> frozenset[str]:
        return frozenset(self._loaders)

    def get(self, file_name: str) -> DocumentLoader:
        extension = PurePath(file_name).suffix.lower()
        try:
            return self._loaders[extension]
        except KeyError:
            raise UnsupportedFileType() from None


def default_loader_registry() -> LoaderRegistry:
    return LoaderRegistry({".txt": TextLoader(), ".pdf": PdfLoader()})
