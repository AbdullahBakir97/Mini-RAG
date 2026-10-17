import pytest

TEXT = "\n\n".join(f"Paragraph {i} about retrieval and generation." for i in range(5))
CONTENT = TEXT.encode()


def upload(client, project, name="notes.txt", content=CONTENT, content_type="text/plain"):
    response = client.post(f"/api/v1/data/upload/{project}",
                           files={"file": (name, content, content_type)})
    assert response.status_code == 200
    return response.json()["file_id"]


def process(client, project, file_id, **options):
    response = client.post(f"/api/v1/data/process/{project}", json={"file_id": file_id, **options})
    assert response.status_code == 200
    return response.json()


def test_full_flow_upload_process_and_read_back(client):
    file_id = upload(client, "demo", name="my notes.txt")
    process(client, "demo", file_id, chunk_size=60, overlap_size=0)

    project = client.get("/api/v1/projects/demo").json()
    files = client.get("/api/v1/projects/demo/files").json()
    chunks = client.get(f"/api/v1/projects/demo/files/{file_id}/chunks").json()

    assert project["name"] == "demo" and project["files_count"] == 1
    assert project["chunks_count"] == chunks["total"] == 5
    assert files["total"] == 1
    [file] = files["items"]
    assert (file["file_id"], file["original_name"], file["content_type"], file["size_bytes"]) == (
        file_id, "my notes.txt", "text/plain", len(CONTENT))
    assert [c["chunk_index"] for c in chunks["items"]] == [0, 1, 2, 3, 4]
    assert chunks["items"][0] == {"chunk_index": 0, "text": "Paragraph 0 about retrieval and generation.",
                                  "metadata": {"source": file_id}}


def test_lists_are_paged(client):
    file_ids = [upload(client, "demo") for _ in range(3)]
    process(client, "demo", file_ids[0], chunk_size=60, overlap_size=0)

    files = client.get("/api/v1/projects/demo/files", params={"offset": 1, "limit": 1}).json()
    chunks = client.get(f"/api/v1/projects/demo/files/{file_ids[0]}/chunks",
                        params={"offset": 3, "limit": 10}).json()

    assert (files["total"], files["offset"], files["limit"]) == (3, 1, 1)
    assert [f["file_id"] for f in files["items"]] == [file_ids[1]]
    assert (chunks["total"], [c["chunk_index"] for c in chunks["items"]]) == (5, [3, 4])


def test_unprocessed_file_has_no_chunks(client):
    file_id = upload(client, "demo")

    chunks = client.get(f"/api/v1/projects/demo/files/{file_id}/chunks").json()

    assert chunks == {"total": 0, "offset": 0, "limit": 20, "items": []}


@pytest.mark.parametrize("path", [
    "/api/v1/projects/nope",
    "/api/v1/projects/nope/files",
    "/api/v1/projects/nope/files/abc_x.txt/chunks",
])
def test_unknown_project(client, path):
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"signal": "project_not_found"}


def test_unknown_file(client):
    upload(client, "demo")

    response = client.get("/api/v1/projects/demo/files/abc_missing.txt/chunks")

    assert response.status_code == 404
    assert response.json() == {"signal": "file_not_found"}


def test_files_of_other_projects_are_not_visible(client):
    file_id = upload(client, "first")
    upload(client, "second")

    assert client.get(f"/api/v1/projects/second/files/{file_id}/chunks").status_code == 404
    assert client.get("/api/v1/projects/second/files").json()["total"] == 1


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 101}])
def test_paging_limits_are_validated(client, params):
    upload(client, "demo")

    assert client.get("/api/v1/projects/demo/files", params=params).status_code == 422
