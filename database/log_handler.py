"""Save log lines to the app_logs table, so /api/v1/admin/logs can show them.

Only the API and the worker save logs (the CLI prints them, as before).
Records are written by a background thread, so logging never slows a request,
and a database problem never breaks the app.
"""

import copy
import logging
import queue
import traceback
from datetime import datetime, timedelta, timezone
from logging.handlers import QueueHandler, QueueListener

from sqlalchemy import delete

from database.engine import session
from database.models import AppLog
from utils.config import get_settings
from utils.logger import RequestContextFilter, get_logger

_MAX_MESSAGE_CHARS = 10_000
_listener: QueueListener | None = None


class _DatabaseHandler(logging.Handler):
    def __init__(self, source: str):
        super().__init__()
        self.source = source

    def emit(self, record: logging.LogRecord) -> None:
        try:
            with session() as db:
                db.add(AppLog(
                    created_at=datetime.fromtimestamp(record.created, timezone.utc),
                    level=record.levelname,
                    level_number=record.levelno,
                    logger=record.name[:100],
                    message=record.getMessage()[:_MAX_MESSAGE_CHARS],
                    exception=record.exc_text,
                    request_id=getattr(record, "request_id", None),
                    source=self.source,
                ))
                db.commit()
        except Exception:
            pass  # never let saving a log line break the app


class _KeepTraceback(QueueHandler):
    """Like QueueHandler, but keeps the message and the traceback apart (QueueHandler
    merges the traceback into the message)."""

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        exception = record.exc_text
        if record.exc_info:
            exception = "".join(traceback.format_exception(*record.exc_info))
        record = copy.copy(record)
        record.msg = record.getMessage()  # the arguments may not survive the trip to the other thread
        record.args = None
        record.exc_info = None
        record.exc_text = exception
        return record


def enable_database_logging(source: str) -> None:
    """Also save log lines of LOG_DB_LEVEL and above to the database."""
    global _listener
    if _listener is not None:
        return
    get_logger(__name__)  # make sure the console logging is set up first
    records: queue.Queue = queue.Queue(-1)
    handler = _KeepTraceback(records)
    handler.setLevel(get_settings().log_db_level.upper())
    handler.addFilter(RequestContextFilter())  # read the request ID in the thread that logged
    logging.getLogger().addHandler(handler)
    _listener = QueueListener(records, _DatabaseHandler(source))
    _listener.start()


def disable_database_logging() -> None:
    """Write the log lines still waiting, then stop."""
    global _listener
    if _listener is not None:
        _listener.stop()
        _listener = None


def delete_old_logs(days: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with session() as db:
        deleted = db.execute(delete(AppLog).where(AppLog.created_at < cutoff)).rowcount
        db.commit()
    return deleted
