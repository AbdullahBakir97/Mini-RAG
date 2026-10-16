import pytest

from controllers import DataController


def upload(client, project_id, name="notes.txt", content=b"hello", content_type="text/plain"):
    return client.post(
        f"/api/v1/data/upload/{project_id}",
        files={"file": (name, content, content_type)},
    )


def test_welcome_returns_app_info(client):
    response = client.get("/api/v1/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello All",
        "app_name": "mini-RAG-test",
        "app_version": "0.0.1",
    }


def test_upload_stores_file_under_project(client, files_dir):
    response = upload(client, "project_1", name="my notes.txt", content=b"some text")

    assert response.status_code == 200
    body = response.json()
    assert body["signal"] == "file_uploaded_successfully"
    assert body["file_id"].endswith("_my_notes.txt")
    assert (files_dir / "project_1" / body["file_id"]).read_bytes() == b"some text"


def test_upload_generates_unique_file_ids(client):
    first = upload(client, "p1").json()["file_id"]
    second = upload(client, "p1").json()["file_id"]

    assert first != second


def test_upload_rejects_unsupported_type(client, files_dir):
    response = upload(client, "p1", name="image.png", content_type="image/png")

    assert response.status_code == 400
    assert response.json() == {"signal": "file_type_not_supported"}
    assert not (files_dir / "p1").exists()


def test_upload_rejects_oversized_file(client):
    # FILE_MAX_SIZE is 1 MB in the test settings.
    response = upload(client, "p1", content=b"x" * (1024 * 1024 + 1))

    assert response.status_code == 400
    assert response.json() == {"signal": "file_size_exceeded"}


@pytest.mark.parametrize("project_id", ["%2E%2E", "a.b", "x" * 65])
def test_upload_rejects_unsafe_project_id(client, files_dir, project_id):
    response = upload(client, project_id)

    assert response.status_code == 422
    assert list(files_dir.parent.glob("*.txt")) == []


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("my notes.txt", "my_notes.txt"),
        ("  padded name.txt  ", "padded_name.txt"),
        ("../../etc/passwd", "....etcpasswd"),
        ("résumé (final).pdf", "résumé_final.pdf"),
    ],
)
def test_get_clean_file_name(original, expected):
    assert DataController().get_clean_file_name(orig_file_name=original) == expected
