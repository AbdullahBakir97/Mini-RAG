import pytest
from pydantic import ValidationError

from mini_rag.core.config import Settings


def test_defaults_use_openai_small_model():
    settings = Settings()

    assert settings.EMBEDDING_BASE_URL is None
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.EMBEDDING_DIMENSIONS == 1536
    assert settings.EMBEDDING_BATCH_SIZE == 64


def test_empty_base_url_means_the_default_server(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BASE_URL", "")

    assert Settings().EMBEDDING_BASE_URL is None


@pytest.mark.parametrize(("api_key", "base_url", "configured"), [
    ("sk-test", "", True),
    ("", "http://localhost:11434/v1", True),  # e.g. Ollama needs no key
    ("", "", False),
])
def test_embeddings_need_a_key_or_a_server(monkeypatch, api_key, base_url, configured):
    monkeypatch.setenv("OPEN_API_KEY", api_key)
    monkeypatch.setenv("EMBEDDING_BASE_URL", base_url)

    assert Settings().embeddings_configured is configured


@pytest.mark.parametrize("name, value", [
    ("EMBEDDING_DIMENSIONS", "0"),
    ("EMBEDDING_DIMENSIONS", "3072"),  # above the HNSW index limit
    ("EMBEDDING_BATCH_SIZE", "0"),
])
def test_embedding_numbers_are_validated(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()
