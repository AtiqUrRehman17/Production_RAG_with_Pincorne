"""One shared logging setup so every module logs in the same format."""

import logging
import sys

from utils.config import get_settings
from utils.request_context import current_request_id

# request_tag is " [<request id>]" in the API and the worker, empty in the CLI
_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s%(request_tag)s | %(message)s"
_configured = False


class RequestContextFilter(logging.Filter):
    """Adds the current request ID to every log record (see utils/request_context.py)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = current_request_id()
        record.request_tag = f" [{record.request_id}]" if record.request_id else ""
        return True


def _configure() -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%H:%M:%S"))
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.setLevel(get_settings().log_level.upper())
    root.addHandler(handler)

    # Third-party libraries are very chatty at INFO level
    for noisy in ("httpx", "httpcore", "urllib3", "google_genai", "pinecone"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
