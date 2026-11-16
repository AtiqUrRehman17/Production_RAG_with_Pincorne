"""Read LangSmith traces for the admin endpoints.

The LangSmith key stays on the server: the frontend asks this API, never LangSmith.
All LangSmith calls are in this file, so moving to a newer LangSmith API later
(list_runs / read_run are deprecated in favour of client.runs) touches only here.
"""

import warnings
from datetime import datetime, timedelta, timezone
from typing import Any

from api.errors import APIError
from api.schemas.admin import TraceDetail, TraceStep, TraceSummary
from utils.exceptions import LangSmithError
from utils.logger import get_logger
from utils.tracing import tracing_enabled, tracing_project

logger = get_logger(__name__)

_DEFAULT_DAYS = 7
_MAX_TEXT_CHARS = 2000  # long inputs / outputs (passages) are shortened
_MAX_LIST_ITEMS = 25


def _client():
    from evaluation.langsmith_dataset import langsmith_client

    if not tracing_enabled():
        raise APIError(503, "tracing_off", "LangSmith tracing is off: set LANGSMITH_TRACING=true in .env.")
    try:
        return langsmith_client()
    except LangSmithError as exc:
        raise APIError(503, "langsmith_not_configured", str(exc)) from exc


def _shorten(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= _MAX_TEXT_CHARS else value[:_MAX_TEXT_CHARS] + f"... ({len(value)} characters)"
    if isinstance(value, dict):
        return {key: _shorten(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        items = [_shorten(item) for item in value[:_MAX_LIST_ITEMS]]
        if len(value) > _MAX_LIST_ITEMS:
            items.append(f"... and {len(value) - _MAX_LIST_ITEMS} more")
        return items
    return value


def _question(run) -> str | None:
    inputs = run.inputs or {}
    question = inputs.get("question") or inputs.get("query") or inputs.get("input")
    return question if isinstance(question, str) else None


def _summary(run) -> dict:
    metadata = run.metadata or {}
    return {
        "id": str(run.id), "name": run.name, "status": run.status, "error": run.error,
        "start_time": run.start_time, "end_time": run.end_time, "latency_seconds": run.latency,
        "total_tokens": run.total_tokens, "tags": run.tags or [],
        "request_id": metadata.get("request_id"), "conversation_id": metadata.get("thread_id"),
        "question": _question(run), "url": getattr(run, "url", None),
    }


def _step(run) -> TraceStep:
    return TraceStep(
        id=str(run.id), name=run.name, run_type=run.run_type, status=run.status, error=run.error,
        start_time=run.start_time, latency_seconds=run.latency, total_tokens=run.total_tokens,
        inputs=_shorten(run.inputs), outputs=_shorten(run.outputs),
        steps=[_step(child) for child in sorted(run.child_runs or [], key=lambda r: r.start_time)],
    )


def _metadata_filter(key: str, value: str) -> str:
    return f'and(eq(metadata_key, "{key}"), eq(metadata_value, "{value}"))'


def list_traces(errors_only: bool = False, min_seconds: float | None = None, since: datetime | None = None,
                conversation_id: str | None = None, request_id: str | None = None,
                limit: int = 20) -> list[TraceSummary]:
    """The latest traces (newest first). Values in filters are checked by the router."""
    filters = []
    if min_seconds:
        filters.append(f'gt(latency, "{min_seconds:g}s")')
    if conversation_id:
        filters.append(_metadata_filter("thread_id", conversation_id))
    if request_id:
        filters.append(_metadata_filter("request_id", request_id))
    query_filter = None
    if filters:
        query_filter = filters[0] if len(filters) == 1 else f"and({', '.join(filters)})"

    client = _client()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            runs = list(client.list_runs(
                project_name=tracing_project(), is_root=True, error=True if errors_only else None,
                start_time=since or datetime.now(timezone.utc) - timedelta(days=_DEFAULT_DAYS),
                filter=query_filter, limit=limit,
            ))
    except Exception as exc:
        logger.warning("Could not list LangSmith traces: %s", exc)
        raise APIError(502, "langsmith_error", "Could not read traces from LangSmith. Check LANGSMITH_API_KEY, "
                                               "LANGSMITH_PROJECT and your internet connection.") from exc
    return [TraceSummary(**_summary(run)) for run in runs]


def get_trace(trace_id: str) -> TraceDetail:
    """One trace with all its steps (rewrite, retrieval, rerank, answer...)."""
    from langsmith.utils import LangSmithNotFoundError

    client = _client()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            run = client.read_run(trace_id, load_child_runs=True)
    except LangSmithNotFoundError as exc:
        raise APIError(404, "trace_not_found", f"No trace with ID {trace_id} was found. "
                                               "New traces can take a few seconds to appear.") from exc
    except Exception as exc:
        logger.warning("Could not read LangSmith trace %s: %s", trace_id, exc)
        raise APIError(502, "langsmith_error", "Could not read the trace from LangSmith.") from exc
    return TraceDetail(
        **_summary(run), metadata=_shorten(run.metadata or {}), inputs=_shorten(run.inputs),
        outputs=_shorten(run.outputs),
        steps=[_step(child) for child in sorted(run.child_runs or [], key=lambda r: r.start_time)],
    )
