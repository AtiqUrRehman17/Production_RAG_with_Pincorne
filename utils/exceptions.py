"""Custom errors. Each one carries a message that is safe to show to the user."""


class RAGError(Exception):
    """Base class for all errors raised by this app."""


class FileValidationError(RAGError):
    """The uploaded file failed a validation check (type, size, corrupt, etc.)."""


class DuplicateDocumentError(RAGError):
    """The exact same file was already uploaded by this user."""

    def __init__(self, message: str, existing_document_id: str):
        super().__init__(message)
        self.existing_document_id = existing_document_id


class DocumentLoadError(RAGError):
    """The file passed validation but its text could not be extracted."""


class EmbeddingError(RAGError):
    """The embedding API failed or returned unexpected vectors."""


class VectorStoreError(RAGError):
    """Pinecone could not be reached, is misconfigured, or an operation failed."""


class ConfigurationError(RAGError):
    """A setting in .env is invalid (e.g. an unknown model name)."""


class LLMError(RAGError):
    """The chat model request failed."""


class DocumentNotFoundError(RAGError):
    """No document with this ID exists for this user."""


class LangSmithError(RAGError):
    """LangSmith is not configured, could not be reached, or an operation failed."""


class JudgeError(RAGError):
    """The AI judge (RAGAS) is misconfigured or could not grade the answers."""


class AuthError(RAGError):
    """Login, registration or account problem. `code` tells the frontend which one;
    `status` is the HTTP status the API answers with."""

    def __init__(self, message: str, code: str, status: int = 401):
        super().__init__(message)
        self.code = code
        self.status = status
