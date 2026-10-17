import pytest
from fastapi.testclient import TestClient

from mini_rag.core.config import get_settings

TEST_ENV = {
    "APP_NAME": "mini-RAG-test",
    "APP_VERSION": "0.0.1",
    "OPEN_API_KEY": "test-key",
    "FILE_ALLOWED_TYPES": '["text/plain", "application/pdf"]',
    "FILE_MAX_SIZE": "1",
    "FILE_DEFAULT_CHUNK_SIZE": "1024",
}


@pytest.fixture
def files_dir(tmp_path):
    """Temporary storage root for uploaded files."""
    return tmp_path / "files"


@pytest.fixture(autouse=True)
def settings_env(monkeypatch, files_dir):
    """Provide settings via env vars instead of a local .env file."""
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("FILES_DIR", str(files_dir))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def build_pdf(pages: list[str]) -> bytes:
    """Build a minimal valid PDF with one page per string (lines split on \\n)."""
    def escape(line):
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        lines = " ".join(f"({escape(line)}) Tj T*" for line in text.split("\n") if line)
        stream = f"BT /F1 12 Tf 72 720 Td 14 TL {lines} ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))

    pdf = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_offset = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref_offset)
    return pdf


@pytest.fixture
def make_pdf():
    return build_pdf


@pytest.fixture
def client():
    from mini_rag.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
