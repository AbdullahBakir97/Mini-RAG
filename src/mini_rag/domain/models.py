from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


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
    # Hex SHA-256 of the content; None for files uploaded before it was kept.
    content_sha256: str | None = None


@dataclass(frozen=True)
class AnswerRecord:
    """What one answer used and cost. The question and the answer text are not kept.

    ``model`` is None when no source matched and the model was not called.
    Token counts are None when the provider did not report them, and
    ``cost_usd`` when they or the model's prices are unknown.
    """

    project_id: int
    prompt_version: str
    model: str | None
    streamed: bool
    answered: bool
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None


@dataclass(frozen=True)
class UsageTotals:
    """A project's answers added up; ``unpriced_answers`` model calls have no known cost."""

    answers: int
    answered: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    unpriced_answers: int


@dataclass(frozen=True)
class Conversation:
    """Questions and answers that follow on from each other. ``id`` is a UUID string."""

    id: str
    project_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class StoredCitation:
    """A source an answer in a conversation cited, kept as it was then."""

    number: int
    file_key: str
    chunk_index: int
    page: int | None
    score: float
    text: str
    section: str | None = None  # Answers stored before sections were read have none.


@dataclass(frozen=True)
class Feedback:
    """What someone thought of an answer: thumbs up or down, and why."""

    rating: Literal["up", "down"]
    comment: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class ConversationMessage:
    """A question (user) or an answer (assistant) in a conversation.

    An answer's ``content`` is None when the documents did not answer.
    ``search_question`` is the standalone question an answer was searched
    with, when it differs from the question asked.
    """

    role: Literal["user", "assistant"]
    content: str | None
    citations: list[StoredCitation] = field(default_factory=list)
    prompt_version: str | None = None
    search_question: str | None = None
    created_at: datetime | None = None
    # Set once stored.
    id: int | None = None
    feedback: Feedback | None = None


@dataclass(frozen=True)
class RatedAnswer:
    """An answer someone rated, with the question it answered."""

    conversation_id: str
    message_id: int
    question: str
    answer: str | None
    citations: list[StoredCitation]
    feedback: Feedback


@dataclass(frozen=True)
class FeedbackCounts:
    up: int = 0
    down: int = 0


@dataclass(frozen=True)
class SearchFilters:
    """Narrows a search to some of a project's chunks; empty fields do not narrow it.

    ``file_keys`` limits it to those files; the page range applies to chunks
    with a page (PDFs), so it leaves out all others; the upload dates are
    the files'; ``metadata`` keeps chunks whose metadata contains it.
    ``max_per_file`` keeps results from crowding into one file.
    """

    file_keys: tuple[str, ...] = ()
    page_from: int | None = None
    page_to: int | None = None
    uploaded_after: datetime | None = None
    uploaded_before: datetime | None = None
    metadata: Mapping[str, Any] | None = None
    max_per_file: int | None = None
