"""Request and response models, and the shared ID types used by routes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import Path, Query
from pydantic import BaseModel, Field, field_validator, model_validator

from mini_rag.core.errors import AppError
from mini_rag.domain.models import SearchFilters
from mini_rag.domain.signals import ResponseSignal

ProjectId = Annotated[str, Path(
    pattern=r"^[A-Za-z0-9_-]{1,64}$",
    description="Project name: letters, digits, '_' and '-' (1-64 characters).",
)]

FILE_ID_PATTERN = r"^[\w.]+$"
FILE_ID_DESCRIPTION = "The file_id returned by the upload endpoint."
# What the docs show for a file_id, so it looks like one the upload returned.
FILE_ID_EXAMPLE = "a16q20nzrtvj_notes.txt"
QUESTION_EXAMPLE = "What do my notes say about overlap?"

FileId = Annotated[str, Field(pattern=FILE_ID_PATTERN, max_length=255,
                              description=FILE_ID_DESCRIPTION, examples=[FILE_ID_EXAMPLE])]
FileIdPath = Annotated[str, Path(pattern=FILE_ID_PATTERN, max_length=255,
                                 description=FILE_ID_DESCRIPTION)]


@dataclass
class Pagination:
    """Shared offset/limit query parameters for list endpoints."""

    offset: Annotated[int, Query(ge=0, description="Items to skip.")] = 0
    limit: Annotated[int, Query(ge=1, le=100, description="Items to return (1-100).")] = 20


def signal_field(signal: ResponseSignal, **kwargs: Any) -> Any:
    """A response's ``signal`` field, shown in the docs with the signal it carries."""
    return Field(examples=[signal.value], **kwargs)


class ErrorResponse(BaseModel):
    signal: ResponseSignal


def error_responses(*errors: type[AppError]) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entries for the errors a route can raise, grouped by status.

    Each signal is a named example, so the docs show the real error bodies.
    """
    signals: dict[int, list[str]] = {}
    for error in errors:
        signals.setdefault(int(error.status_code), []).append(error.signal.value)
    return {
        status: {
            "model": ErrorResponse,
            "description": "Signal: " + ", ".join(f"`{signal}`" for signal in status_signals),
            "content": {"application/json": {"examples": {
                signal: {"value": {"signal": signal}} for signal in status_signals}}},
        }
        for status, status_signals in signals.items()
    }


class HealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    database: Literal["ok", "unavailable"]


class WelcomeResponse(BaseModel):
    message: str
    app_name: str
    app_version: str


class UploadResponse(BaseModel):
    signal: ResponseSignal = signal_field(ResponseSignal.FILE_UPLOAD_SUCCESS)
    file_id: str = Field(examples=[FILE_ID_EXAMPLE])


class ProcessRequest(BaseModel):
    file_id: FileId
    chunk_size: int = Field(default=1000, gt=0, le=100_000,
                            description="Maximum chunk length in characters, overlap included.")
    overlap_size: int = Field(default=200, ge=0,
                              description="Characters of preceding text repeated at the start of each chunk.")

    @model_validator(mode="after")
    def check_overlap_smaller_than_chunk(self):
        if self.overlap_size >= self.chunk_size:
            raise ValueError("overlap_size must be smaller than chunk_size")
        return self


class ProcessResponse(BaseModel):
    signal: ResponseSignal = signal_field(ResponseSignal.PROCESSING_SUCCESS)
    file_id: str = Field(examples=[FILE_ID_EXAMPLE])
    chunks_count: int


class IndexRequest(BaseModel):
    file_id: FileId | None = Field(default=None,
                                   description="Index only this file; omit for the whole project.")


class IndexResponse(BaseModel):
    signal: ResponseSignal = signal_field(ResponseSignal.INDEXING_SUCCESS)
    embedded_count: int = Field(description="Chunks embedded by this request.")
    chunks_count: int = Field(description="All chunks of the project, or of the file.")


class SearchFiltersRequest(BaseModel):
    """Narrows the chunks searched; leave a field out not to narrow by it."""

    file_ids: list[FileId] = Field(default_factory=list, max_length=100,
                                   description="Only these files of the project.")
    page_from: int | None = Field(default=None, ge=1,
                                  description="Only pages from this one on; leaves out chunks "
                                              "without a page (not from a PDF).")
    page_to: int | None = Field(default=None, ge=1, description="Only pages up to this one.")
    uploaded_after: datetime | None = Field(default=None,
                                            description="Only files uploaded at or after this.")
    uploaded_before: datetime | None = Field(default=None,
                                             description="Only files uploaded before this.")
    metadata: dict[str, str | int | float | bool] | None = Field(
        default=None, max_length=10,
        description="Only chunks whose metadata has these values, e.g. {\"page\": 3}.")
    max_per_file: int | None = Field(default=None, ge=1, le=50,
                                     description="At most this many results from one file.")

    @model_validator(mode="after")
    def check_ranges(self) -> "SearchFiltersRequest":
        if self.page_from and self.page_to and self.page_from > self.page_to:
            raise ValueError("page_from must not be after page_to")
        if (self.uploaded_after and self.uploaded_before
                and self.uploaded_after >= self.uploaded_before):
            raise ValueError("uploaded_after must be before uploaded_before")
        return self

    def to_filters(self) -> SearchFilters:
        return SearchFilters(file_keys=tuple(self.file_ids), page_from=self.page_from,
                             page_to=self.page_to, uploaded_after=self.uploaded_after,
                             uploaded_before=self.uploaded_before, metadata=self.metadata,
                             max_per_file=self.max_per_file)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="The question or search text.",
                       examples=[QUESTION_EXAMPLE])
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of results.")
    min_score: float | None = Field(default=None, ge=-1, le=1,
                                    description="Leave out results scoring below this.")
    filters: SearchFiltersRequest | None = None

    @field_validator("query")
    @classmethod
    def query_must_contain_text(cls, query: str) -> str:
        if not query.strip():
            raise ValueError("query must not be blank")
        return query


class SearchResult(BaseModel):
    file_id: str
    chunk_index: int
    score: float = Field(description="Cosine similarity to the query: 1 is the best match.")
    text: str
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    signal: ResponseSignal = signal_field(ResponseSignal.SEARCH_SUCCESS)
    results: list[SearchResult]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="The question to answer.",
                          examples=[QUESTION_EXAMPLE])
    top_k: int = Field(default=5, ge=1, le=20, description="Most chunks to answer from.")
    min_score: float | None = Field(
        default=None, ge=-1, le=1,
        description="Leave out chunks scoring below this; omit for the server's ANSWER_MIN_SCORE.")
    conversation_id: UUID | None = Field(
        default=None,
        description="Answer as a follow-up in this conversation, and add the question and the "
                    "answer to it. Omit for a question on its own.")
    filters: SearchFiltersRequest | None = Field(
        default=None, description="Answer only from the chunks these filters leave.")

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, question: str) -> str:
        if not question.strip():
            raise ValueError("question must not be blank")
        return question


class CitationResponse(BaseModel):
    number: int = Field(description="The [n] marker that cites this source in the answer.")
    file_id: str
    chunk_index: int
    page: int | None = Field(description="Page number for PDFs, starting at 1; null otherwise.")
    score: float = Field(description="Cosine similarity to the question: 1 is the best match.")
    text: str


class UsageResponse(BaseModel):
    input_tokens: int | None = Field(description="Prompt tokens; 0 when the model was not called, "
                                                 "null when the provider did not report them.")
    output_tokens: int | None = Field(description="Tokens the model wrote, as for input_tokens.")
    cost_usd: float | None = Field(description="US dollars; null when the usage or the model's "
                                               "prices (LLM_*_PRICE_PER_MILLION) are unknown.")


class AskResponse(BaseModel):
    signal: ResponseSignal = signal_field(
        ResponseSignal.ANSWER_SUCCESS, description="`answer_success`, or `no_answer` when the documents do not answer the question.")
    answer: str | None = Field(description="The answer with [n] citation markers; null for `no_answer`.")
    citations: list[CitationResponse] = Field(description="The sources the answer cites, in order of first citation.")
    prompt_version: str = Field(description="The prompt that produced the answer, e.g. `answer-v1`.")
    usage: UsageResponse = Field(description="Tokens and cost of this answer, including the "
                                             "rewriting of a follow-up question.")
    conversation_id: str | None = Field(
        default=None, description="The conversation the question was asked in, if any.")
    search_question: str | None = Field(
        default=None, description="In a conversation: the standalone question the sources were "
                                  "searched with, when the follow-up had to be rewritten.")
    message_id: int | None = Field(
        default=None, description="In a conversation: the answer's message, to rate it with "
                                  "PUT .../messages/{message_id}/feedback.")


class ProjectResponse(BaseModel):
    name: str
    created_at: datetime
    files_count: int
    chunks_count: int
    embedded_chunks_count: int = Field(
        description="Chunks that are indexed for search; equals chunks_count when the index is complete.")


class ProjectListItem(BaseModel):
    name: str
    created_at: datetime


class ProjectListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ProjectListItem]


class ProjectUsageResponse(BaseModel):
    answers: int = Field(description="Questions asked, streamed or not.")
    answered: int = Field(description="Of those, how many got an answer rather than `no_answer`.")
    input_tokens: int = Field(description="Prompt tokens of all answers that reported usage.")
    output_tokens: int = Field(description="Tokens the model wrote, likewise.")
    cost_usd: float = Field(description="US dollars of all answers with a known cost.")
    unpriced_answers: int = Field(description="Model calls whose cost is unknown and not "
                                              "included in cost_usd.")


class FileResponse(BaseModel):
    file_id: str
    original_name: str
    content_type: str
    size_bytes: int
    created_at: datetime


class FileListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[FileResponse]


class ChunkResponse(BaseModel):
    chunk_index: int
    text: str
    metadata: dict[str, Any]


class ChunkListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ChunkResponse]


ConversationIdPath = Annotated[UUID, Path(description="The conversation's id.")]
MessageIdPath = Annotated[int, Path(ge=1, description="The answer's message id.")]


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200,
                              description="Omit to title it after the first question.")


class ConversationResponse(BaseModel):
    id: str
    title: str | None = Field(description="Null until the first question.")
    created_at: datetime
    updated_at: datetime = Field(description="When the last question was answered.")


class ConversationListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ConversationResponse]


class FeedbackRequest(BaseModel):
    rating: Literal["up", "down"] = Field(description="Thumbs up or down.")
    comment: str | None = Field(default=None, max_length=1000,
                                description="What was good or wrong, in a few words.")


class FeedbackResponse(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None
    created_at: datetime


class MessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str | None = Field(description="Null for an answer when the documents did not answer.")
    citations: list[CitationResponse] = Field(description="The sources an answer cited.")
    prompt_version: str | None
    search_question: str | None = Field(
        description="The standalone question an answer was searched with, when rewritten.")
    created_at: datetime
    feedback: FeedbackResponse | None = Field(default=None, description="An answer's rating, if any.")


class RatedAnswerResponse(BaseModel):
    conversation_id: str
    message_id: int
    question: str = Field(description="The question the answer answered.")
    answer: str | None = Field(description="Null when the documents did not answer.")
    citations: list[CitationResponse]
    feedback: FeedbackResponse


class FeedbackListResponse(BaseModel):
    up: int = Field(description="Answers rated thumbs up in the project.")
    down: int = Field(description="Answers rated thumbs down in the project.")
    total: int = Field(description="Rated answers matching the filter.")
    offset: int
    limit: int
    items: list[RatedAnswerResponse]


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = Field(description="Questions and answers, oldest first.")
