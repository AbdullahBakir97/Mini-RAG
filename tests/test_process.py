import pytest

TEXT = (
    "Retrieval-augmented generation combines search with a language model.\n\n"
    "Documents are split into chunks, indexed, and retrieved per question."
)


def upload(client, project_id, name, content, content_type):
    response = client.post(
        f"/api/v1/data/upload/{project_id}",
        files={"file": (name, content, content_type)},
    )
    assert response.status_code == 200
    return response.json()["file_id"]


def process(client, project_id, file_id, **options):
    return client.post(
        f"/api/v1/data/process/{project_id}",
        json={"file_id": file_id, **options},
    )


def test_process_txt_returns_single_chunk_by_default(client):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")

    response = process(client, "p1", file_id)

    assert response.status_code == 200
    body = response.json()
    assert body["signal"] == "processing_success"
    assert body["file_id"] == file_id
    assert body["chunks_count"] == 1
    assert body["chunks"] == [
        {"text": TEXT, "metadata": {"source": file_id, "chunk_index": 0}}
    ]


def test_process_txt_respects_chunk_size(client):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")

    body = process(client, "p1", file_id, chunk_size=40, overlap_size=10).json()

    assert body["chunks_count"] == len(body["chunks"]) > 1
    assert all(len(chunk["text"]) <= 40 for chunk in body["chunks"])
    assert [c["metadata"]["chunk_index"] for c in body["chunks"]] == list(
        range(body["chunks_count"]))


def test_process_pdf_keeps_page_numbers(client, make_pdf):
    pdf = make_pdf(["Page one talks about embeddings.", "Page two covers vector search."])
    file_id = upload(client, "p1", "guide.pdf", pdf, "application/pdf")

    body = process(client, "p1", file_id).json()

    assert body["signal"] == "processing_success"
    assert [(c["text"], c["metadata"]["page"]) for c in body["chunks"]] == [
        ("Page one talks about embeddings.", 1),
        ("Page two covers vector search.", 2),
    ]


def test_process_pdf_without_text(client, make_pdf):
    file_id = upload(client, "p1", "scan.pdf", make_pdf([""]), "application/pdf")

    response = process(client, "p1", file_id)

    assert response.status_code == 400
    assert response.json() == {"signal": "file_has_no_text"}


def test_process_corrupt_pdf(client):
    file_id = upload(client, "p1", "broken.pdf", b"not really a pdf", "application/pdf")

    response = process(client, "p1", file_id)

    assert response.status_code == 400
    assert response.json() == {"signal": "processing_failed"}


def test_process_unsupported_extension(client):
    file_id = upload(client, "p1", "notes.md", b"# heading", "text/plain")

    response = process(client, "p1", file_id)

    assert response.status_code == 400
    assert response.json() == {"signal": "file_type_not_supported"}


@pytest.mark.parametrize("file_id", ["missing.txt", "..", "."])
def test_process_missing_file(client, file_id):
    upload(client, "p1", "notes.txt", b"text", "text/plain")

    response = process(client, "p1", file_id)

    assert response.status_code == 404
    assert response.json() == {"signal": "file_not_found"}


def test_process_cannot_read_other_projects(client):
    file_id = upload(client, "p1", "notes.txt", b"secret", "text/plain")

    response = process(client, "p2", file_id)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"file_id": "../p2/notes.txt"},
        {"file_id": "a/b.txt"},
        {"file_id": ""},
        {"file_id": "x.txt", "chunk_size": 0},
        {"file_id": "x.txt", "chunk_size": 100, "overlap_size": 100},
        {"file_id": "x.txt", "overlap_size": -1},
    ],
)
def test_process_rejects_invalid_request(client, payload):
    response = client.post("/api/v1/data/process/p1", json=payload)

    assert response.status_code == 422
