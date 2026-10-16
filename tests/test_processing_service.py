import pytest

from mini_rag.core.errors import (
    FileNotFound,
    NoTextExtracted,
    ProcessingFailed,
    UnsupportedFileType,
)
from mini_rag.domain.models import Document
from mini_rag.loaders.registry import LoaderRegistry
from mini_rag.services.processing_service import ProcessingService
from mini_rag.storage.file_storage import FileStorage


class FakeLoader:
    def __init__(self, documents=None, error=None):
        self.documents, self.error, self.calls = documents or [], error, []

    def load(self, path, source):
        self.calls.append((path, source))
        if self.error:
            raise self.error
        return self.documents


@pytest.fixture
def storage(tmp_path):
    return FileStorage(root=tmp_path / "files")


def make_service(storage, loader):
    return ProcessingService(storage=storage, loaders=LoaderRegistry({".txt": loader}))


def test_chunks_carry_document_metadata_and_a_running_index(storage):
    loader = FakeLoader([
        Document("alpha beta gamma delta", {"source": "s", "page": 1}),
        Document("epsilon zeta", {"source": "s", "page": 2}),
    ])
    file_id, path = storage.reserve_file("p1", "a.txt")

    chunks = make_service(storage, loader).process("p1", file_id, chunk_size=12, overlap_size=0)

    assert loader.calls == [(path, file_id)]
    assert [(c.index, c.text, c.metadata) for c in chunks] == [
        (0, "alpha beta", {"source": "s", "page": 1}),
        (1, "gamma delta", {"source": "s", "page": 1}),
        (2, "epsilon zeta", {"source": "s", "page": 2}),
    ]


def test_missing_file_is_reported_before_loading(storage):
    loader = FakeLoader()

    with pytest.raises(FileNotFound):
        make_service(storage, loader).process("p1", "nope.txt", 100, 0)
    assert loader.calls == []


def test_unsupported_type(storage):
    file_id, _ = storage.reserve_file("p1", "a.md")

    with pytest.raises(UnsupportedFileType):
        make_service(storage, FakeLoader()).process("p1", file_id, 100, 0)


def test_loader_errors_become_processing_failed_with_cause(storage):
    file_id, _ = storage.reserve_file("p1", "a.txt")
    cause = RuntimeError("corrupt")

    with pytest.raises(ProcessingFailed) as raised:
        make_service(storage, FakeLoader(error=cause)).process("p1", file_id, 100, 0)
    assert raised.value.__cause__ is cause


def test_blank_documents_raise_no_text(storage):
    file_id, _ = storage.reserve_file("p1", "a.txt")
    loader = FakeLoader([Document("   "), Document("\n\n")])

    with pytest.raises(NoTextExtracted):
        make_service(storage, loader).process("p1", file_id, 100, 0)
