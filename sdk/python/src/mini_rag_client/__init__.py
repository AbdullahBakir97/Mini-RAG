"""A Python client for the Mini RAG API, generated from its OpenAPI schema.

    from mini_rag_client import MiniRag

    with MiniRag("https://rag.example.com", api_key="mrag_…") as rag:
        rag.add_document("handbook", "leave-policy.pdf", tags=["hr"])
        answer = rag.ask_project("handbook", question="How many days of leave?")
"""

from . import models
from ._types import UNSET, Unset
from .client import AnswerDelta, AnswerDone, AnswerEvent, AsyncMiniRag, MiniRag
from .errors import MiniRagError

__all__ = ["UNSET", "AnswerDelta", "AnswerDone", "AnswerEvent", "AsyncMiniRag", "MiniRag",
           "MiniRagError", "Unset", "models"]
__version__ = "0.1.0"
