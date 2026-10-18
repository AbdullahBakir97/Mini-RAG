import time
from dataclasses import dataclass

from mini_rag.domain.repositories import UnitOfWork
from mini_rag.evaluation.dataset import Dataset
from mini_rag.evaluation.metrics import CaseResult, judge
from mini_rag.services.indexing_service import IndexingService
from mini_rag.services.processing_service import ProcessingService
from mini_rag.services.search_service import SearchService
from mini_rag.services.upload_service import UploadService


@dataclass(frozen=True)
class RetrievalRun:
    results: list[CaseResult]
    chunks: int
    seconds: dict[str, float]


class _Bytes:
    """An in-memory file to upload."""

    def __init__(self, data: bytes):
        self.data = data

    async def read(self, size: int = -1) -> bytes:
        size = len(self.data) if size < 0 else size
        piece, self.data = self.data[:size], self.data[size:]
        return piece


def project_name(dataset: Dataset) -> str:
    """The project a dataset is evaluated in.

    The dots keep it apart from every project created through the API,
    whose names cannot contain them.
    """
    return f"eval.{dataset.name}.{dataset.version}"


class EvaluationService:
    """Measures retrieval on a dataset through the same steps as the API.

    The documents are uploaded, split, indexed and searched in a project of
    their own, which is deleted afterwards, also when the run fails. Their
    files stay in the upload service's storage; `mini-rag eval` gives it a
    temporary folder.
    """

    def __init__(self, uow: UnitOfWork, upload: UploadService, processing: ProcessingService,
                 indexing: IndexingService, search: SearchService):
        self.uow = uow
        self.upload = upload
        self.processing = processing
        self.indexing = indexing
        self.search = search

    async def run_retrieval(self, dataset: Dataset, *, top_k: int, chunk_size: int,
                            overlap_size: int) -> RetrievalRun:
        project = project_name(dataset)
        # A run that was killed may have left its project behind.
        await self._delete(project)
        try:
            started = time.perf_counter()
            names: dict[str, str] = {}
            chunks = 0
            for document in dataset.documents:
                key = await self.upload.save(project, document.name, document.content_type,
                                             _Bytes(document.path.read_bytes()))
                names[key] = document.name
                chunks += await self.processing.process(project, key, chunk_size=chunk_size,
                                                        overlap_size=overlap_size)
            processed = time.perf_counter()
            await self.indexing.index(project)
            indexed = time.perf_counter()

            results = []
            for case in dataset.cases:
                # Every result counts, however low it scores: the metrics apply
                # the minimum score themselves.
                hits = await self.search.search(project, case.question, top_k=top_k)
                results.append(judge(case, [(names[hit.file_key], hit) for hit in hits]))
            searched = time.perf_counter()
        finally:
            await self.uow.rollback()
            await self._delete(project)
        return RetrievalRun(results=results, chunks=chunks, seconds={
            "processing": processed - started, "indexing": indexed - processed,
            "search": searched - indexed})

    async def _delete(self, project: str) -> None:
        if await self.uow.projects.delete(project):
            await self.uow.commit()
