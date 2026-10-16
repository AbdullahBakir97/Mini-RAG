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
class UnembeddedChunk:
    """A stored chunk that has no embedding yet. ``id`` is its database ID."""

    id: int
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    """A search hit: a chunk, the file_id of its file and how well it matches.

    ``score`` is the cosine similarity to the query: 1 means the same
    direction, 0 unrelated.
    """

    file_key: str
    chunk: Chunk
    score: float


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
