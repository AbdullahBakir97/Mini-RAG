"""The interface services use to generate text with a language model.

Implementations live in mini_rag.llm; tests use a scripted fake.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Message:
    """One message of a chat: instructions (system), a request (user) or a reply."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLM(Protocol):

    model: str

    async def complete(self, messages: Sequence[Message]) -> str:
        """The model's reply to the conversation in ``messages``."""
        ...

    def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        """The same reply, in pieces as the model writes it."""
        ...
