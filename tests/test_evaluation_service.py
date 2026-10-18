import pytest

from mini_rag.core.errors import EmbeddingFailed
from mini_rag.evaluation.dataset import load_dataset
from mini_rag.loaders.registry import default_loader_registry
from mini_rag.services.evaluation_service import EvaluationService, project_name
from mini_rag.services.indexing_service import IndexingService
from mini_rag.services.processing_service import ProcessingService
from mini_rag.services.search_service import SearchService
from mini_rag.services.upload_service import UploadService
from mini_rag.storage.file_storage import FileStorage

from .fakes import FakeEmbedder, FakeUnitOfWork
from .test_eval_dataset import CAT, write_dataset

pytestmark = pytest.mark.anyio


def service(uow, embedder, files):
    storage = FileStorage(root=files)
    return EvaluationService(
        uow=uow,
        upload=UploadService(storage=storage, uow=uow, allowed_types=["text/plain"],
                             max_bytes=1_000_000, read_size=1024),
        processing=ProcessingService(storage=storage, loaders=default_loader_registry(), uow=uow),
        indexing=IndexingService(uow=uow, embedder=embedder, batch_size=16),
        search=SearchService(uow=uow, embedder=embedder))


async def test_runs_each_question_through_upload_processing_indexing_and_search(tmp_path):
    dataset = load_dataset(write_dataset(tmp_path / "dataset", [CAT]))
    uow = FakeUnitOfWork()

    run = await service(uow, FakeEmbedder(), tmp_path / "files").run_retrieval(
        dataset, top_k=3, chunk_size=1000, overlap_size=0)

    [result] = run.results
    assert result.first_relevant.file == "notes.txt"
    assert result.reciprocal_rank == 1.0
    assert run.chunks == 1
    assert set(run.seconds) == {"processing", "indexing", "search"}
    # The project is only there for the run.
    assert await uow.projects.get_by_name(project_name(dataset)) is None


async def test_the_project_is_deleted_when_the_run_fails(tmp_path):
    dataset = load_dataset(write_dataset(tmp_path / "dataset", [CAT]))
    uow = FakeUnitOfWork()

    with pytest.raises(EmbeddingFailed):
        await service(uow, FakeEmbedder(fail_on_call=1), tmp_path / "files").run_retrieval(
            dataset, top_k=3, chunk_size=1000, overlap_size=0)

    assert await uow.projects.get_by_name(project_name(dataset)) is None


async def test_a_project_left_by_an_earlier_run_is_replaced(tmp_path):
    dataset = load_dataset(write_dataset(tmp_path / "dataset", [CAT]))
    uow = FakeUnitOfWork()
    left = await uow.projects.get_or_create(project_name(dataset))

    await service(uow, FakeEmbedder(), tmp_path / "files").run_retrieval(
        dataset, top_k=3, chunk_size=1000, overlap_size=0)

    assert await uow.files.count_for_project(left.id) == 0
