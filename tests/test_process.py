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


CHUNKS_SQL = "SELECT chunk_index, text, metadata FROM chunks ORDER BY chunk_index"


def test_process_returns_a_summary_and_stores_the_chunks(client, query):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")

    response = process(client, "p1", file_id)

    assert response.status_code == 200
    assert response.json() == {"signal": "processing_success", "file_id": file_id, "chunks_count": 1}
    assert query(CHUNKS_SQL) == [(0, TEXT, {"source": file_id})]


def test_process_respects_chunk_size(client, query):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")

    body = process(client, "p1", file_id, chunk_size=40, overlap_size=10).json()

    stored = query(CHUNKS_SQL)
    assert body["chunks_count"] == len(stored) > 1
    assert all(len(text) <= 40 for _, text, _ in stored)
    assert [index for index, _, _ in stored] == list(range(len(stored)))


def test_process_pdf_keeps_page_numbers(client, query, make_pdf):
    pdf = make_pdf(["Page one talks about embeddings.", "Page two covers vector search."])
    file_id = upload(client, "p1", "guide.pdf", pdf, "application/pdf")

    process(client, "p1", file_id)

    assert [(text, meta["page"]) for _, text, meta in query(CHUNKS_SQL)] == [
        ("Page one talks about embeddings.", 1),
        ("Page two covers vector search.", 2),
    ]


def test_processing_again_replaces_the_chunks(client, query):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")
    first = process(client, "p1", file_id, chunk_size=40, overlap_size=0).json()["chunks_count"]

    second = process(client, "p1", file_id).json()["chunks_count"]

    assert first > 1 and second == 1
    assert query("SELECT count(*) FROM chunks") == [(1,)]


def test_failed_processing_keeps_the_previous_chunks(client, query, files_dir):
    file_id = upload(client, "p1", "notes.txt", TEXT.encode(), "text/plain")
    process(client, "p1", file_id)
    (files_dir / "p1" / file_id).write_text("   ")  # now has no text

    response = process(client, "p1", file_id)

    assert response.json() == {"signal": "file_has_no_text"}
    assert query(CHUNKS_SQL) == [(0, TEXT, {"source": file_id})]


def test_file_on_disk_without_a_record_is_not_found(client, files_dir):
    (files_dir / "p1").mkdir(parents=True)
    (files_dir / "p1" / "abc_stray.txt").write_text("not uploaded through the API")

    assert process(client, "p1", "abc_stray.txt").status_code == 404


def test_process_pdf_without_text(client, make_pdf):
    file_id = upload(client, "p1", "scan.pdf", make_pdf([""]), "application/pdf")

    response = process(client, "p1", file_id)

    assert response.status_code == 422
    assert response.json() == {"signal": "file_has_no_text"}


def test_process_corrupt_pdf(client):
    file_id = upload(client, "p1", "broken.pdf", b"not really a pdf", "application/pdf")

    response = process(client, "p1", file_id)

    assert response.status_code == 422
    assert response.json() == {"signal": "processing_failed"}


def test_process_unsupported_extension(client):
    file_id = upload(client, "p1", "notes.md", b"# heading", "text/plain")

    response = process(client, "p1", file_id)

    assert response.status_code == 415
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
