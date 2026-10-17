from mini_rag.core.errors import NoTextExtracted, ProcessingFailed
from mini_rag.domain.models import Chunk, Document
from mini_rag.loaders.registry import LoaderRegistry
from mini_rag.storage.file_storage import FileStorage
from mini_rag.text.splitter import RecursiveTextSplitter


class ProcessingService:
    """Turns a stored file into chunks: find it, load it, split it."""

    def __init__(self, storage: FileStorage, loaders: LoaderRegistry):
        self.storage = storage
        self.loaders = loaders

    def process(self, project_id: str, file_id: str,
                chunk_size: int, overlap_size: int) -> list[Chunk]:
        path = self.storage.get_file_path(project_id, file_id)
        loader = self.loaders.get(file_id)
        splitter = RecursiveTextSplitter(chunk_size=chunk_size, overlap_size=overlap_size)

        try:
            documents = loader.load(path, source=file_id)
        except Exception as exc:
            raise ProcessingFailed(f"Could not read {file_id}") from exc

        chunks = self._split(documents, splitter)
        if not chunks:
            raise NoTextExtracted()
        return chunks

    @staticmethod
    def _split(documents: list[Document], splitter: RecursiveTextSplitter) -> list[Chunk]:
        chunks: list[Chunk] = []
        for document in documents:
            for text in splitter.split(document.text):
                metadata = {**document.metadata, "chunk_index": len(chunks)}
                chunks.append(Chunk(text=text, metadata=metadata))
        return chunks
