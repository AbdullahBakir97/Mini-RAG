import asyncio

import pytest

from mini_rag.core.errors import FileTooLarge, UnsupportedFileType, UploadFailed
from mini_rag.services.upload_service import UploadService
from mini_rag.storage.file_storage import FileStorage


class FakeStream:
    """Serves `data` in reads; optionally fails after `fail_after` reads."""

    def __init__(self, data: bytes, fail_after: int | None = None,
                 error: BaseException | None = None):
        self.data, self.fail_after, self.reads = data, fail_after, 0
        self.error = error or OSError("disk failure")

    async def read(self, size: int = -1) -> bytes:
        if self.fail_after is not None and self.reads >= self.fail_after:
            raise self.error
        self.reads += 1
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


@pytest.fixture
def storage(tmp_path):
    return FileStorage(root=tmp_path / "files")


@pytest.fixture
def service(storage):
    return UploadService(storage=storage, allowed_types=["text/plain"],
                         max_bytes=100, read_size=10)


def save(service, data=b"hello", content_type="text/plain", declared_size=None,
         **stream_options):
    stream = FakeStream(data, **stream_options)
    return asyncio.run(service.save("p1", "notes.txt", content_type, stream,
                                    declared_size=declared_size))


def stored_files(storage):
    return [path for path in storage.root.rglob("*") if path.is_file()]


def test_save_streams_file_to_storage(service, storage):
    data = b"x" * 95

    file_id = save(service, data)

    assert storage.get_file_path("p1", file_id).read_bytes() == data


def test_rejects_unsupported_type_before_touching_disk(service, storage):
    with pytest.raises(UnsupportedFileType):
        save(service, content_type="image/png")

    assert not storage.root.exists()


def test_rejects_declared_size_over_limit(service, storage):
    with pytest.raises(FileTooLarge):
        save(service, declared_size=101)

    assert stored_files(storage) == []


def test_enforces_limit_on_bytes_actually_received(service, storage):
    # The client claims 5 bytes (or nothing) but sends 101.
    for declared in (5, None):
        with pytest.raises(FileTooLarge):
            save(service, b"x" * 101, declared_size=declared)

    assert stored_files(storage) == []


def test_exactly_the_limit_is_accepted(service, storage):
    file_id = save(service, b"x" * 100)

    assert storage.get_file_path("p1", file_id).stat().st_size == 100


def test_stream_failure_becomes_upload_failed_and_cleans_up(service, storage):
    with pytest.raises(UploadFailed) as raised:
        save(service, b"x" * 50, fail_after=2)

    assert isinstance(raised.value.__cause__, OSError)
    assert stored_files(storage) == []


def test_cancelled_upload_leaves_nothing_behind(service, storage):
    with pytest.raises(asyncio.CancelledError):
        save(service, b"x" * 50, fail_after=1, error=asyncio.CancelledError())

    assert stored_files(storage) == []
