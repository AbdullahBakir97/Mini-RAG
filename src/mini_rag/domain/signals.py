from enum import Enum


class ResponseSignal(Enum):

    FILE_TYPES_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_uploaded_successfully"
    FILE_UPLOAD_FAILED = "file_upload_failed"
    FILE_NOT_FOUND = "file_not_found"
    PROJECT_NOT_FOUND = "project_not_found"
    FILE_HAS_NO_TEXT = "file_has_no_text"
    PROCESSING_SUCCESS = "processing_success"
    PROCESSING_FAILED = "processing_failed"
    INDEXING_SUCCESS = "indexing_success"
    SEARCH_SUCCESS = "search_success"
    ANSWER_SUCCESS = "answer_success"
    NO_ANSWER = "no_answer"
    CONVERSATION_NOT_FOUND = "conversation_not_found"
    EMBEDDING_NOT_CONFIGURED = "embedding_not_configured"
    EMBEDDING_FAILED = "embedding_failed"
    LLM_NOT_CONFIGURED = "llm_not_configured"
    LLM_FAILED = "llm_failed"
