"""Application errors.

Each error carries the response signal and HTTP status it maps to, so the
code that detects a problem only raises it, and a single handler in the API
layer turns it into a response.
"""

from http import HTTPStatus

from mini_rag.domain.signals import ResponseSignal


class AppError(Exception):
    """Base class for errors that are reported to API clients."""

    signal: ResponseSignal
    status_code: HTTPStatus = HTTPStatus.BAD_REQUEST

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.signal.value)


class UnsupportedFileType(AppError):
    signal = ResponseSignal.FILE_TYPES_NOT_SUPPORTED
    status_code = HTTPStatus.UNSUPPORTED_MEDIA_TYPE


class FileTooLarge(AppError):
    signal = ResponseSignal.FILE_SIZE_EXCEEDED
    status_code = HTTPStatus.REQUEST_ENTITY_TOO_LARGE


class UploadFailed(AppError):
    signal = ResponseSignal.FILE_UPLOAD_FAILED
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR


class FileNotFound(AppError):
    signal = ResponseSignal.FILE_NOT_FOUND
    status_code = HTTPStatus.NOT_FOUND


class ProjectNotFound(AppError):
    signal = ResponseSignal.PROJECT_NOT_FOUND
    status_code = HTTPStatus.NOT_FOUND


class ConversationNotFound(AppError):
    signal = ResponseSignal.CONVERSATION_NOT_FOUND
    status_code = HTTPStatus.NOT_FOUND


class NoTextExtracted(AppError):
    signal = ResponseSignal.FILE_HAS_NO_TEXT
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class ProcessingFailed(AppError):
    signal = ResponseSignal.PROCESSING_FAILED
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class EmbeddingNotConfigured(AppError):
    """Neither an API key nor an embedding server is configured."""

    signal = ResponseSignal.EMBEDDING_NOT_CONFIGURED
    status_code = HTTPStatus.SERVICE_UNAVAILABLE


class EmbeddingFailed(AppError):
    """The embedding provider failed or returned something unusable."""

    signal = ResponseSignal.EMBEDDING_FAILED
    status_code = HTTPStatus.BAD_GATEWAY


class LLMNotConfigured(AppError):
    """Neither an API key nor a language model server is configured."""

    signal = ResponseSignal.LLM_NOT_CONFIGURED
    status_code = HTTPStatus.SERVICE_UNAVAILABLE


class LLMFailed(AppError):
    """The language model provider failed or returned something unusable."""

    signal = ResponseSignal.LLM_FAILED
    status_code = HTTPStatus.BAD_GATEWAY
