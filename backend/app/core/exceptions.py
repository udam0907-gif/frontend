from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application exception."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: Any = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404
    error_code = "NOT_FOUND"


class ValidationError(AppError):
    status_code = 422
    error_code = "VALIDATION_ERROR"


class TemplateError(AppError):
    status_code = 422
    error_code = "TEMPLATE_ERROR"


class TemplateStructureViolationError(AppError):
    """Raised when LLM or input would rearrange template structure."""
    status_code = 422
    error_code = "TEMPLATE_STRUCTURE_VIOLATION"


class MissingDocumentError(AppError):
    status_code = 422
    error_code = "MISSING_DOCUMENT"


class DocumentGenerationError(AppError):
    status_code = 500
    error_code = "DOCUMENT_GENERATION_ERROR"


class LLMServiceError(AppError):
    status_code = 502
    error_code = "LLM_SERVICE_ERROR"


class EmbeddingError(AppError):
    status_code = 502
    error_code = "EMBEDDING_ERROR"


class RagNoEvidenceError(AppError):
    """Raised when RAG cannot find evidence above confidence threshold."""
    status_code = 200
    error_code = "RAG_NO_EVIDENCE"


class StorageError(AppError):
    status_code = 500
    error_code = "STORAGE_ERROR"


class ConflictError(AppError):
    status_code = 409
    error_code = "CONFLICT"


class ParseError(AppError):
    status_code = 422
    error_code = "PARSE_ERROR"


class MappingNotFoundError(AppError):
    """vendor_template_pool에 cell_map이 없을 때 — 출력 차단."""
    status_code = 422
    error_code = "MAPPING_NOT_FOUND"
