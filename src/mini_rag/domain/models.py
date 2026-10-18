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
    """A collection of documents, owned by one tenant.

    ``folder`` is where its files are stored: the name in the default
    tenant, so files uploaded before tenants existed stay where they are.
    """

    id: int
    name: str
    created_at: datetime
    tenant_id: int | None = None
    storage_name: str | None = None

    @property
    def folder(self) -> str:
        return self.storage_name or self.name


DEFAULT_TENANT = "default"
# What an API key may do. Each route needs one of them.
SCOPES = ("read", "write", "ask", "admin")
Scope = Literal["read", "write", "ask", "admin"]


@dataclass(frozen=True)
class Tenant:
    """An organisation or app with its own projects, invisible to other tenants.

    Its limits override the server's defaults; None keeps the default, 0 is unlimited.
    """

    id: int
    name: str
    created_at: datetime
    requests_per_minute: int | None = None
    answers_per_month: int | None = None
    storage_mb: int | None = None


@dataclass(frozen=True)
class Limits:
    """What a tenant may use; 0 is unlimited."""

    requests_per_minute: int = 0
    answers_per_month: int = 0
    storage_mb: int = 0


@dataclass(frozen=True)
class TenantUsage:
    """What a tenant used this calendar month (UTC), and the storage it holds now."""

    period_start: datetime
    answers: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    storage_bytes: int


@dataclass(frozen=True)
class ApiKey:
    """A tenant's API key. Only its hash is stored; ``prefix`` identifies it in lists."""

    id: str
    tenant_id: int
    name: str
    prefix: str
    scopes: tuple[str, ...]
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class Principal:
    """Who a request acts for: a tenant, with the scopes its key has."""

    tenant_id: int
    tenant_name: str
    scopes: frozenset[str]
    key_id: str | None = None  # None when authentication is off.


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


JobStatus = Literal["queued", "running", "succeeded", "failed"]
JobStage = Literal["processing", "indexing"]


@dataclass(frozen=True)
class Job:
    """Processing and indexing one file in the background.

    A job is ``queued``, then ``running`` (``stage`` says which step, and
    ``progress`` goes from 0 to 1 while chunks are indexed), then
    ``succeeded`` or ``failed``. A failure that may pass, such as the
    embedding provider being down, queues it again until ``max_attempts``.
    """

    id: str
    project_id: int
    project_name: str
    file_id: int
    file_key: str
    chunk_size: int
    overlap_size: int
    status: JobStatus
    attempts: int
    max_attempts: int
    created_at: datetime
    stage: JobStage | None = None
    progress: float = 0.0
    chunks_count: int | None = None
    error_signal: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # The tenant that owns its project; the worker acts for it.
    tenant_id: int | None = None


# What webhooks can subscribe to; "ping" is sent on request, to any webhook.
WEBHOOK_EVENTS = ("file.uploaded", "file.deleted", "job.succeeded", "job.failed")


@dataclass(frozen=True)
class Webhook:
    """A URL that hears about a project's events, signed with ``secret``."""

    id: str
    project_id: int
    url: str
    events: tuple[str, ...]
    secret: str
    created_at: datetime
    description: str | None = None


DeliveryStatus = Literal["pending", "delivered", "failed"]


@dataclass(frozen=True)
class WebhookDelivery:
    """One event sent to one webhook: tried until it is delivered or out of attempts.

    ``payload`` is fixed when the event happens; each attempt signs it anew.
    """

    id: str
    webhook_id: str
    event: str
    payload: dict[str, Any]
    status: DeliveryStatus
    attempts: int
    created_at: datetime
    next_attempt_at: datetime | None = None
    response_status: int | None = None
    error: str | None = None
    delivered_at: datetime | None = None

