"""The ID of the request (API) or job (worker) being handled right now.

The same ID is returned to the caller, written on every log line and saved on
the LangSmith trace, so one ID finds everything that happened for a request.
"""

import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def current_request_id() -> str | None:
    return request_id_var.get()
