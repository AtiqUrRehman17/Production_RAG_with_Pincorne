"""Debugging (admin only, X-Admin-Key header): app logs, LangSmith traces, health numbers, all jobs.

Start from an error the user saw ("ref: 3f2a..."): search the logs by that
request ID, then open its trace to see which step failed.
"""

from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies import get_db, require_admin
from api.errors import APIError
from api.pagination import MAX_LIMIT, paginate
from api.routers.jobs import JobStatus, JobType, list_jobs_page
from api.schemas.admin import LogOut, StatsOut, TraceDetail, TraceSummary
from api.schemas.common import Page
from api.schemas.documents import JobOut
from api.services import traces
from database.models import AppLog, Feedback, Job, Message

router = APIRouter(prefix="/admin", tags=["admin: monitoring"], dependencies=[Depends(require_admin)])

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_REQUEST_ID = r"^[A-Za-z0-9_-]{8,64}$"
_UUID = r"^[0-9a-fA-F-]{36}$"


@router.get("/logs", response_model=Page[LogOut], summary="App logs from the API and the worker, newest first")
def list_logs(
    level: str = Query("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="This level and above"),
    request_id: str | None = Query(None, pattern=_REQUEST_ID),
    q: str | None = Query(None, max_length=200, description="Text the message contains"),
    source: str | None = Query(None, pattern="^(api|worker)$"),
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
    db: Session = Depends(get_db),
) -> Page[LogOut]:
    query = select(AppLog).where(AppLog.level_number >= _LEVELS[level])
    if request_id:
        query = query.where(AppLog.request_id == request_id)
    if q:
        query = query.where(AppLog.message.contains(q))
    if source:
        query = query.where(AppLog.source == source)
    if since:
        query = query.where(AppLog.created_at >= since)
    if until:
        query = query.where(AppLog.created_at <= until)
    rows, next_cursor = paginate(db, query, AppLog.id, AppLog.id, limit, cursor)
    return Page(items=[LogOut.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.get("/traces", response_model=list[TraceSummary], summary="Recent LangSmith traces, newest first")
def list_traces(
    errors_only: bool = False,
    min_seconds: float | None = Query(None, gt=0, description="Only traces slower than this"),
    since: datetime | None = Query(None, description="Default: the last 7 days"),
    conversation_id: str | None = Query(None, pattern=_UUID),
    request_id: str | None = Query(None, pattern=_REQUEST_ID),
    limit: int = Query(20, ge=1, le=MAX_LIMIT),
) -> list[TraceSummary]:
    return traces.list_traces(errors_only, min_seconds, since, conversation_id, request_id, limit)


@router.get("/traces/{trace_id}", response_model=TraceDetail, summary="One trace, step by step")
def get_trace(trace_id: str) -> TraceDetail:
    if len(trace_id) != 36:
        raise APIError(404, "trace_not_found", f"No trace with ID {trace_id} was found.")
    return traces.get_trace(trace_id)


@router.get("/stats", response_model=StatsOut, summary="Health numbers for the last N hours")
def stats(hours: int = Query(24, ge=1, le=24 * 30), db: Session = Depends(get_db)) -> StatsOut:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    answers = list(db.execute(select(Message.status, Message.found, Message.latency_ms).where(
        Message.role == "assistant", Message.created_at >= since)))
    latencies = sorted(a.latency_ms for a in answers if a.status == "complete" and a.latency_ms is not None)
    complete = [a for a in answers if a.status == "complete"]
    questions = {
        "total": len(answers),
        "answered": sum(1 for a in complete if a.found),
        "not_found": sum(1 for a in complete if a.found is False),
        "errors": sum(1 for a in answers if a.status == "error"),
        "not_found_rate": round(sum(1 for a in complete if a.found is False) / len(complete), 3) if complete else None,
        "avg_latency_ms": round(mean(latencies)) if latencies else None,
        "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else None,
    }
    ratings = dict(db.execute(select(Feedback.rating, func.count()).where(Feedback.updated_at >= since)
                              .group_by(Feedback.rating)).all())
    job_counts = {f"{row.type}_{row.status}": row.count for row in db.execute(
        select(Job.type, Job.status, func.count().label("count")).where(Job.created_at >= since)
        .group_by(Job.type, Job.status))}
    log_counts = dict(db.execute(select(AppLog.level, func.count()).where(
        AppLog.created_at >= since, AppLog.level_number >= _LEVELS["WARNING"]).group_by(AppLog.level)).all())
    recent_errors = db.scalars(select(AppLog).where(AppLog.created_at >= since, AppLog.level_number >= _LEVELS["ERROR"])
                               .order_by(AppLog.id.desc()).limit(5))
    return StatsOut(
        hours=hours, questions=questions, feedback={"up": ratings.get(1, 0), "down": ratings.get(-1, 0)},
        jobs=job_counts, logs={"errors": log_counts.get("ERROR", 0) + log_counts.get("CRITICAL", 0),
                               "warnings": log_counts.get("WARNING", 0)},
        recent_errors=[LogOut.model_validate(row) for row in recent_errors],
    )


@router.get("/jobs", response_model=Page[JobOut], summary="All jobs of every user (incl. evaluations)")
def list_all_jobs(
    status: list[JobStatus] | None = Query(None),
    type: JobType | None = None,
    limit: int = Query(20, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
    db: Session = Depends(get_db),
) -> Page[JobOut]:
    return list_jobs_page(db, limit, cursor, status, type, user_id=None)


@router.get("/jobs/{job_id}", response_model=JobOut, summary="Any job, by ID")
def get_any_job(job_id: str, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None:
        raise APIError(404, "job_not_found", f"No job with ID {job_id} was found.")
    return JobOut.model_validate(job)
