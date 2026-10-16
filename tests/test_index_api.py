import pytest

from mini_rag.api.dependencies import get_embedder

from .fakes import FakeEmbedder

TEXT = "\n\n".join(f"Paragraph {i} about retrieval and generation." for i in range(5))


@pytest.fixture
def embedder(client):
    fake = FakeEmbedder()
    client.app.dependency_overrides[get_embedder] = lambda: fake
    return fake


def upload_and_process(client, project="demo", name="notes.txt", text=TEXT):
    response = client.post(f"/api/v1/data/upload/{project}",
                           files={"file": (name, text.encode(), "text/plain")})
    file_id = response.json()["file_id"]
    response = client.post(f"/api/v1/data/process/{project}",
                           json={"file_id": file_id, "chunk_size": 60, "overlap_size": 0})
    assert response.status_code == 200
    return file_id


def test_index_embeds_new_chunks_and_is_repeatable(client, embedder, query):
    upload_and_process(client)

    first = client.post("/api/v1/index/demo")
    second = client.post("/api/v1/index/demo")

    assert first.status_code == 200
    assert first.json() == {"signal": "indexing_success", "embedded_count": 5, "chunks_count": 5}
    assert second.json() == {"signal": "indexing_success", "embedded_count": 0, "chunks_count": 5}
    assert query("SELECT count(*) FROM chunks WHERE embedding IS NOT NULL") == [(5,)]


def test_index_a_single_file(client, embedder):
    upload_and_process(client)
    file_id = upload_and_process(client, text="Just one paragraph.")

    response = client.post("/api/v1/index/demo", json={"file_id": file_id})

    assert response.json() == {"signal": "indexing_success", "embedded_count": 1, "chunks_count": 1}


def test_reprocessing_a_file_needs_indexing_again(client, embedder):
    file_id = upload_and_process(client)
    client.post("/api/v1/index/demo")

    client.post("/api/v1/data/process/demo",
                json={"file_id": file_id, "chunk_size": 1000, "overlap_size": 0})

    assert client.post("/api/v1/index/demo").json()["embedded_count"] == 1


@pytest.mark.parametrize(("path", "body", "status", "signal"), [
    ("/api/v1/index/missing", None, 404, "project_not_found"),
    ("/api/v1/index/demo", {"file_id": "nope.txt"}, 404, "file_not_found"),
])
def test_index_unknown_project_or_file(client, embedder, path, body, status, signal):
    upload_and_process(client)

    response = client.post(path, json=body)

    assert (response.status_code, response.json()) == (status, {"signal": signal})


def test_index_invalid_file_id(client, embedder):
    response = client.post("/api/v1/index/demo", json={"file_id": "../etc/passwd"})

    assert response.status_code == 422


def test_index_reports_embedding_failures(client):
    # Each test gets a new app, so the override needs no cleanup.
    client.app.dependency_overrides[get_embedder] = lambda: FakeEmbedder(fail_on_call=1)
    upload_and_process(client)

    response = client.post("/api/v1/index/demo")

    assert (response.status_code, response.json()) == (502, {"signal": "embedding_failed"})


def test_index_without_embedding_configuration(client):
    upload_and_process(client)
    client.app.state.embedder = None

    response = client.post("/api/v1/index/demo")

    assert (response.status_code, response.json()) == (503, {"signal": "embedding_not_configured"})
