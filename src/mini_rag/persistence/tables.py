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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
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


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
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
