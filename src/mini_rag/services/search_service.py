from typing import Literal

from mini_rag.core.errors import ProjectNotFound
from mini_rag.domain.embedder import Embedder
from mini_rag.domain.models import ScoredChunk
from mini_rag.domain.repositories import UnitOfWork

SearchMode = Literal["hybrid", "vector"]


class SearchService:
    """Finds the chunks of a project that best match a question.

    In hybrid mode, chunks that share the question's words count as well as
    chunks close to it in meaning; in vector mode only meaning counts.
    """

    def __init__(self, uow: UnitOfWork, embedder: Embedder, mode: SearchMode = "hybrid"):
        self.uow = uow
        self.embedder = embedder
        self.mode = mode

    async def search(self, project_name: str, query: str, top_k: int,
                     min_score: float | None = None) -> list[ScoredChunk]:
        """The best matching indexed chunks, best first.

        Chunks that are not indexed yet are not searched. A project with no
        indexed chunks returns no results without calling the embedder.
        """
        project = await self.uow.projects.get_by_name(project_name)
        if project is None:
            raise ProjectNotFound()
        if await self.uow.chunks.count_embedded_for_project(project.id) == 0:
            return []

        [vector] = await self.embedder.embed([query])
        return await self.uow.chunks.search(
            project.id, vector, top_k=top_k, min_score=min_score,
            query=query if self.mode == "hybrid" else None)
