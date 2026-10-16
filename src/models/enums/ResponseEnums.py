from enum import Enum


class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS = "file_validated_successfully"
    FILE_TYPES_NOT_SUPPORTED = "file_type_not_supported"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    FILE_UPLOAD_SUCCESS = "file_uploaded_successfully"
    FILE_UPLOAD_FAILED = "file_upload_failed"
