import pytest
from pydantic import ValidationError

from mini_rag.core.config import Settings


def test_defaults_use_openai():
    settings = Settings()

    assert settings.LLM_BASE_URL is None
    assert settings.LLM_MODEL == "gpt-4.1-mini"
    assert settings.LLM_MAX_TOKENS == 1024
    assert settings.LLM_TEMPERATURE is None


@pytest.mark.parametrize("name", ["LLM_BASE_URL", "LLM_TEMPERATURE"])
def test_empty_values_mean_the_default(monkeypatch, name):
    monkeypatch.setenv(name, "")

    assert getattr(Settings(), name) is None


@pytest.mark.parametrize(("api_key", "base_url", "configured"), [
    ("sk-test", "", True),
    ("", "http://localhost:11434/v1", True),  # e.g. Ollama needs no key
    ("", "", False),
])
def test_llm_needs_a_key_or_a_server(monkeypatch, api_key, base_url, configured):
    monkeypatch.setenv("OPENAI_API_KEY", api_key)
    monkeypatch.setenv("LLM_BASE_URL", base_url)

    assert Settings().llm_configured is configured


def test_llm_server_is_independent_of_the_embedding_server(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")

    settings = Settings()

    assert settings.embeddings_configured and not settings.llm_configured


@pytest.mark.parametrize(("name", "value"), [
    ("LLM_MAX_TOKENS", "0"),
    ("LLM_TEMPERATURE", "-0.1"),
    ("LLM_TEMPERATURE", "2.5"),
])
def test_llm_numbers_are_validated(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()
