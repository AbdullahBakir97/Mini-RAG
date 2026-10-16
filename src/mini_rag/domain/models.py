from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Document:
    """Text loaded from a file, such as a whole text file or one PDF page."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A piece of a document, sized for embedding and retrieval.

    ``index`` is the chunk's position within its file, starting at 0.
    """

    index: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Project:
    id: int
    name: str
    created_at: datetime


@dataclass(frozen=True)
class FileRecord:
    """An uploaded file. ``key`` is the file_id clients use."""

    id: int
    project_id: int
    key: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
