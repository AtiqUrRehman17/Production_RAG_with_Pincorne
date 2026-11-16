"""One error format for every endpoint, so the frontend shows errors the same way everywhere:

    {"error": {"code": "invalid_file", "message": "...", "request_id": "...", "details": ...}}

`message` is always safe to show to the user. Unexpected errors never reveal
internals; their details are in the admin logs under the request ID.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from utils.exceptions import (
    AuthError,
    ConfigurationError,
    DocumentLoadError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmbeddingError,
    FileValidationError,
    JudgeError,
    LangSmithError,
    LLMError,
    RAGError,
    VectorStoreError,
)
from utils.request_context import current_request_id


class APIError(Exception):
    """An error raised by the API itself, with its HTTP status."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


# Most specific first: the first matching class wins
_RAG_ERRORS: tuple[tuple[type[RAGError], int, str], ...] = (
    (DuplicateDocumentError, 409, "duplicate_document"),
    (DocumentNotFoundError, 404, "document_not_found"),
    (FileValidationError, 400, "invalid_file"),
    (DocumentLoadError, 422, "unreadable_document"),
    (LLMError, 502, "llm_error"),
    (EmbeddingError, 502, "embedding_error"),
    (VectorStoreError, 502, "vector_store_error"),
    (LangSmithError, 502, "langsmith_error"),
    (JudgeError, 400, "judge_error"),
    (ConfigurationError, 500, "configuration_error"),
    (RAGError, 400, "error"),
)
_HTTP_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
               405: "method_not_allowed", 413: "too_large", 429: "rate_limited"}


def error_body(code: str, message: str, details: Any = None) -> dict:
    error = {"code": code, "message": message, "request_id": current_request_id()}
    if details is not None:
        error["details"] = details
    return {"error": error}


def describe(exc: Exception) -> tuple[int, dict]:
    """HTTP status and error body for an exception (also used by the streaming endpoint)."""
    if isinstance(exc, APIError):
        return exc.status_code, error_body(exc.code, exc.message, exc.details)
    if isinstance(exc, AuthError):
        return exc.status, error_body(exc.code, str(exc))
    if isinstance(exc, RAGError):
        for error_class, status, code in _RAG_ERRORS:
            if isinstance(exc, error_class):
                details = None
                if isinstance(exc, DuplicateDocumentError):
                    details = {"document_id": exc.existing_document_id}
                if isinstance(exc, LLMError) and ("rate limit" in str(exc) or "quota" in str(exc)):
                    status, code = 429, "rate_limited"
                return status, error_body(code, str(exc), details)
    return 500, error_body("internal_error", "Something went wrong on the server. "
                                             "Quote the request ID when reporting this.")


def _json(status: int, body: dict, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, headers=headers)


def _headers(exc: Exception, status: int) -> dict[str, str] | None:
    headers = dict(getattr(exc, "headers", None) or {})
    if status == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")  # tells clients a login is needed
    return headers or None


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    status, body = describe(exc)
    return _json(status, body, _headers(exc, status))


async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
    code = _HTTP_CODES.get(exc.status_code, "error")
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return _json(exc.status_code, error_body(code, message), getattr(exc, "headers", None))


async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [{"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]}
               for error in exc.errors()]
    return _json(422, error_body("validation_error", "Some fields are missing or invalid.", details))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(APIError, _app_error)
    app.add_exception_handler(RAGError, _app_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
