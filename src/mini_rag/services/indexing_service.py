from dataclasses import dataclass

from mini_rag.core.errors import FileNotFound, ProjectNotFound
from mini_rag.domain.embedder import Embedder
from mini_rag.domain.repositories import UnitOfWork


@dataclass(frozen=True)
class IndexResult:
    """``embedded_count`` chunks were embedded now, of ``chunks_count`` in scope."""

    embedded_count: int
    chunks_count: int


class IndexingService:
    """Gives stored chunks an embedding, so that search can find them."""

    def __init__(self, uow: UnitOfWork, embedder: Embedder, batch_size: int):
        self.uow = uow
        self.embedder = embedder
        self.batch_size = batch_size

    async def index(self, project_name: str, file_key: str | None = None) -> IndexResult:
        """Embed the project's chunks, or one file's, that have no embedding yet.

        Each batch is committed on its own: after a failure the work done so
        far is kept, and calling again continues where it stopped. Chunks
        that already have an embedding are never sent again.
        """
        project = await self.uow.projects.get_by_name(project_name)
        if project is None:
            raise ProjectNotFound()
        file_id = None
        if file_key is not None:
            record = await self.uow.files.get_by_key(project.id, file_key)
            if record is None:
                raise FileNotFound()
            file_id = record.id

        embedded = 0
        while pending := await self.uow.chunks.list_unembedded(
                project.id, file_id=file_id, limit=self.batch_size):
            vectors = await self.embedder.embed([chunk.text for chunk in pending])
            await self.uow.chunks.set_embeddings(
                {chunk.id: vector for chunk, vector in zip(pending, vectors, strict=True)})
            await self.uow.commit()
            embedded += len(pending)

        if file_id is None:
            total = await self.uow.chunks.count_for_project(project.id)
        else:
            total = await self.uow.chunks.count_for_file(file_id)
        return IndexResult(embedded_count=embedded, chunks_count=total)
