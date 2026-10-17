import json

import httpx2
import pytest

from mini_rag.core.config import Settings
from mini_rag.core.errors import LLMFailed
from mini_rag.domain.llm import Message
from mini_rag.llm.factory import create_llm
from mini_rag.llm.openai_llm import OpenAILLM

pytestmark = pytest.mark.anyio

MESSAGES = [Message("system", "Be brief."), Message("user", "Hello?")]


class FakeChatServer:
    """Answers POST /chat/completions like the OpenAI API and records the requests."""

    def __init__(self, content="Hi there.", status_code=200, choices=True):
        self.content = content
        self.status_code = status_code
        self.choices = choices
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.status_code != 200:
            return httpx2.Response(self.status_code, json={"error": {"message": "boom"}})
        choices = [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": self.content}}]
        return httpx2.Response(200, json={
            "id": "chatcmpl-1", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": choices if self.choices else [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})

    @property
    def last_body(self):
        return json.loads(self.requests[-1].content)


def make_llm(server, **overrides):
    options = {"api_key": "sk-test", "model": "test-model", "max_tokens": 100,
               "base_url": "http://llm.test/v1", "max_retries": 0,
               "http_client": httpx2.AsyncClient(transport=httpx2.MockTransport(server))}
    return OpenAILLM(**{**options, **overrides})


async def test_sends_the_messages_and_returns_the_reply():
    server = FakeChatServer()

    reply = await make_llm(server).complete(MESSAGES)

    assert reply == "Hi there."
    assert server.requests[0].url == "http://llm.test/v1/chat/completions"
    assert server.requests[0].headers["authorization"] == "Bearer sk-test"
    assert server.last_body == {
        "model": "test-model", "max_tokens": 100,
        "messages": [{"role": "system", "content": "Be brief."},
                     {"role": "user", "content": "Hello?"}]}


async def test_temperature_is_sent_only_when_set():
    server = FakeChatServer()

    await make_llm(server, temperature=0.2).complete(MESSAGES)

    assert server.last_body["temperature"] == 0.2


async def test_openai_itself_gets_max_completion_tokens():
    server = FakeChatServer()
    llm = make_llm(server, base_url=None)
    llm._client = llm._client.with_options(base_url="http://llm.test/v1")

    await llm.complete(MESSAGES)

    assert server.last_body["max_completion_tokens"] == 100
    assert "max_tokens" not in server.last_body


async def test_a_server_without_a_key_gets_a_placeholder():
    server = FakeChatServer()

    await make_llm(server, api_key="").complete(MESSAGES)

    assert server.requests[0].headers["authorization"] == "Bearer not-needed"


@pytest.mark.parametrize("server", [
    FakeChatServer(status_code=500),
    FakeChatServer(status_code=401),
    FakeChatServer(content=None),
    FakeChatServer(content="  \n"),
    FakeChatServer(choices=False),
], ids=["server-error", "bad-key", "no-content", "blank-content", "no-choices"])
async def test_failures_raise_llm_failed(server):
    with pytest.raises(LLMFailed):
        await make_llm(server).complete(MESSAGES)


async def test_unreachable_server_raises_llm_failed():
    def refuse(request):
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(LLMFailed):
        await make_llm(refuse).complete(MESSAGES)


def test_factory_returns_none_without_key_or_server(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")

    assert create_llm(Settings()) is None


def test_factory_uses_the_llm_settings(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "local-model")
    monkeypatch.setenv("LLM_MAX_TOKENS", "256")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.1")

    llm = create_llm(Settings())

    assert (llm.model, llm.max_tokens, llm.temperature) == ("local-model", 256, 0.1)
    assert str(llm._client.base_url) == "http://localhost:11434/v1/"
