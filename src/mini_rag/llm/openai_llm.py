from collections.abc import Sequence
from typing import Any

import httpx2
from openai import AsyncOpenAI, OpenAIError

from mini_rag.core.errors import LLMFailed
from mini_rag.domain.llm import Message

# Servers such as Ollama need no key, but the SDK insists on one.
PLACEHOLDER_API_KEY = "not-needed"


class OpenAILLM:
    """Generates replies with the OpenAI chat completions API or a compatible server.

    Set ``base_url`` for another server, e.g. Ollama at
    http://localhost:11434/v1. ``temperature`` None leaves it to the model,
    which reasoning models require. Transient errors (rate limits, timeouts,
    5xx) are retried by the SDK; anything that still fails, or a reply
    without text, raises LLMFailed.
    """

    def __init__(self, *, api_key: str, model: str, max_tokens: int,
                 temperature: float | None = None, base_url: str | None = None,
                 timeout_seconds: float = 60.0, max_retries: int = 2,
                 http_client: httpx2.AsyncClient | None = None):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        # OpenAI's newer models accept only max_completion_tokens, while
        # compatible servers such as Ollama document only max_tokens.
        self._max_tokens_parameter = "max_tokens" if base_url else "max_completion_tokens"
        self._client = AsyncOpenAI(api_key=api_key or PLACEHOLDER_API_KEY, base_url=base_url,
                                   timeout=timeout_seconds, max_retries=max_retries,
                                   http_client=http_client)

    async def complete(self, messages: Sequence[Message]) -> str:
        options: dict[str, Any] = {self._max_tokens_parameter: self.max_tokens}
        if self.temperature is not None:
            options["temperature"] = self.temperature
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": message.role, "content": message.content}
                          for message in messages],
                **options)
        except OpenAIError as exc:
            raise LLMFailed(f"Chat request to {self.model} failed") from exc

        if not response.choices or not (response.choices[0].message.content or "").strip():
            raise LLMFailed(f"{self.model} returned no text")
        return response.choices[0].message.content

    async def aclose(self) -> None:
        await self._client.close()
