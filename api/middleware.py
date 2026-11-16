"""Gives every request an ID and catches errors nothing else handled.

The ID comes from the caller's X-Request-ID header (if it is a sensible value)
or is made up. It is sent back in the X-Request-ID header and in every error
body, written on every log line, and saved on the request's LangSmith traces.
"""

import json
import re
import time

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.errors import describe
from utils.config import get_settings
from utils.logger import get_logger
from utils.request_context import new_request_id, request_id_var
from utils.tracing import model_labels, trace_scope

logger = get_logger("api.requests")

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{8,64}")
_SLOW_REQUEST_SECONDS = 10


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else new_request_id()
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                status, response_started = message["status"], True
                MutableHeaders(scope=message).append("X-Request-ID", request_id)
            await send(message)

        try:
            metadata = {"request_id": request_id, **model_labels(get_settings())}
            with trace_scope(tags=["api"], metadata=metadata):
                await self.app(scope, receive, send_with_id)
        except Exception as exc:
            logger.exception("Unhandled error in %s %s", scope["method"], scope["path"])
            if not response_started:
                status, body = describe(exc)
                await send_with_id({"type": "http.response.start", "status": status,
                                    "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": json.dumps(body).encode()})
        finally:
            seconds = time.perf_counter() - started
            if status >= 500:
                level = "error"
            elif status >= 400 or seconds > _SLOW_REQUEST_SECONDS:
                level = "warning"
            else:
                level = "debug"
            getattr(logger, level)("%s %s -> %d in %.0f ms", scope["method"], scope["path"], status, seconds * 1000)
            request_id_var.reset(token)
