"""Database tables (SQLAlchemy 2 declarative models).

These are persistence details: the rest of the app works with the domain
models, and the repositories translate between the two.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names, so migrations are reproducible and
# constraints can be referenced (and dropped) by name.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Length of chunks.embedding as the migrations create it. A database can be
# switched to another length with `mini-rag resize-embeddings`, for a model
# with other vectors; EMBEDDING_DIMENSIONS must match the database (checked
# when the app starts).
EMBEDDING_DIMENSIONS = 1536


# The text search configuration of chunks.search_vector.
FULL_TEXT_CONFIG = "english"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class TenantRow(Base):
    """An organisation or app; its projects are invisible to other tenants."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _created_at()


class ApiKeyRow(Base):
    """A tenant's API key: only a SHA-256 of it is kept."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    # The start of the key, to tell keys apart; not enough to use it.
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    created_at: Mapped[datetime] = _created_at()
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectRow(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    # The project's folder under FILES_DIR; unique across tenants.
    storage_name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = _created_at()


class FileRow(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("project_id", "key"),
        # The same content is kept once per project.
        Index("uq_files_project_id_content_sha256", "project_id", "content_sha256", unique=True,
              postgresql_where=text("content_sha256 IS NOT NULL")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # The file_id clients use; also the file name in storage.
    key: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # Hex SHA-256 of the content; NULL for files uploaded before it was kept.
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created_at()


class ChunkRow(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "chunk_index"),
        # Approximate nearest-neighbour search by cosine distance. HNSW needs
        # no training data, so it works from the first row.
        Index("ix_chunks_embedding", "embedding", postgresql_using="hnsw",
              postgresql_ops={"embedding": "vector_cosine_ops"}),
        # Full-text search, the other half of hybrid search.
        Index("ix_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"))
    # Denormalised from files, so per-project queries need no join.
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    # "metadata" is reserved on declarative classes, hence the attribute name.
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default="{}", default=dict)
    # NULL until the chunk is indexed; deleted together with the chunk.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    # The chunk's words, kept up to date by PostgreSQL. English stemming lets
    # "deploys" match "deploy"; words of other languages match as written.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed(f"to_tsvector('{FULL_TEXT_CONFIG}', text)", persisted=True))
    created_at: Mapped[datetime] = _created_at()


class AnswerRow(Base):
    """One answer's usage and cost; the question and answer text are not stored."""

    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    prompt_version: Mapped[str] = mapped_column(String(64))
    # NULL when the model was not called (no source matched).
    model: Mapped[str | None] = mapped_column(String(255))
    streamed: Mapped[bool] = mapped_column(Boolean)
    answered: Mapped[bool] = mapped_column(Boolean)
    # NULL when the provider did not report them.
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    # US dollars; NULL when the tokens or the model's prices are unknown.
    cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 8, asdecimal=False))
    created_at: Mapped[datetime] = _created_at()


class ConversationRow(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_project_id_updated_at", "project_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = _created_at()


class ConversationMessageRow(Base):
    """A question or an answer in a conversation, with the sources the answer cited."""

    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    # NULL for an answer when the documents did not answer.
    content: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default="[]", default=list)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    search_question: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    # Thumbs up or down on an answer, with an optional comment.
    feedback_rating: Mapped[str | None] = mapped_column(String(8))
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("feedback_rating IN ('up', 'down')", name="feedback_rating"),
        Index("ix_conversation_messages_feedback_at", "feedback_at",
              postgresql_where=text("feedback_at IS NOT NULL")),
    )


class JobRow(Base):
    """Processing and indexing one file in the background."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="status"),
        CheckConstraint("stage IN ('processing', 'indexing')", name="stage"),
        Index("ix_jobs_project_id_created_at", "project_id", "created_at"),
        # Workers look for due jobs: queued ones, and running ones whose lease ran out.
        Index("ix_jobs_run_after", "run_after", postgresql_where=text("status = 'queued'")),
        Index("ix_jobs_locked_until", "locked_until", postgresql_where=text("status = 'running'")),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Deleting the file deletes its jobs.
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), index=True)
    chunk_size: Mapped[int] = mapped_column(Integer)
    overlap_size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    stage: Mapped[str | None] = mapped_column(String(16))
    progress: Mapped[float] = mapped_column(Float, server_default="0")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer)
    chunks_count: Mapped[int | None] = mapped_column(Integer)
    # Why the last attempt failed; the details are in the worker's log.
    error_signal: Mapped[str | None] = mapped_column(String(64))
    # A queued job waits until then (retries back off).
    run_after: Mapped[datetime] = _created_at()
    # A running job belongs to its worker until then; after, another may take it.
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookRow(Base):
    """A URL that hears about a project's events."""

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(Text)
    events: Mapped[list[str]] = mapped_column(ARRAY(String(32)))
    # Signs each delivery; kept as is, since signing needs it.
    secret: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class WebhookDeliveryRow(Base):
    """One event sent to one webhook, with the outcome of its last attempt."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'delivered', 'failed')", name="status"),
        Index("ix_webhook_deliveries_webhook_id_created_at", "webhook_id", "created_at"),
        # Dispatchers look for pending deliveries that are due.
        Index("ix_webhook_deliveries_next_attempt_at", "next_attempt_at",
              postgresql_where=text("status = 'pending'")),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    webhook_id: Mapped[str] = mapped_column(ForeignKey("webhooks.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    # When a pending delivery is due; a claimed one is not due again for a while.
    next_attempt_at: Mapped[datetime | None] = _created_at()
    response_status: Mapped[int | None] = mapped_column(Integer)
    # Why the last attempt failed, in our words (never the receiver's reply).
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

