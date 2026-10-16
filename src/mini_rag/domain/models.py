from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    """Text loaded from a file, such as a whole text file or one PDF page."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A piece of a document, sized for embedding and retrieval."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
