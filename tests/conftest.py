import pytest
from fastapi.testclient import TestClient

from controllers.BaseController import BaseController
from helpers.config import get_settings

TEST_ENV = {
    "APP_NAME": "mini-RAG-test",
    "APP_VERSION": "0.0.1",
    "OPEN_API_KEY": "test-key",
    "FILE_ALLOWED_TYPES": '["text/plain", "application/pdf"]',
    "FILE_MAX_SIZE": "1",
    "FILE_DEFAULT_CHUNK_SIZE": "1024",
}


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    """Provide settings via env vars instead of a local .env file."""
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def files_dir(tmp_path, monkeypatch):
    """Redirect uploaded files to a temporary directory."""
    original_init = BaseController.__init__

    def patched_init(self):
        original_init(self)
        self.file_dir = str(tmp_path)

    monkeypatch.setattr(BaseController, "__init__", patched_init)
    return tmp_path


@pytest.fixture
def client(files_dir):
    from main import app

    with TestClient(app) as test_client:
        yield test_client
