"""Job records in the database: what the API shows while the worker does the work.

  queued -> processing -> done
                       -> failed (with a reason that is safe to show)

A job that fails for a passing reason (a network problem, a rate limit) goes
back to queued and is tried again.
"""

from sqlalchemy import select

from database.engine import session
from database.models import Job, utc_now

ACTIVE = ("queued", "processing")


def create_job(type: str, user_id: str, **fields) -> Job:
    with session() as db:
        job = Job(type=type, user_id=user_id, **fields)
        db.add(job)
        db.commit()
        return job


def get_job(job_id: str) -> Job | None:
    with session() as db:
        return db.get(Job, job_id)


def update_job(job_id: str, **fields) -> Job | None:
    with session() as db:
        job = db.get(Job, job_id)
        if job is None:
            return None
        for name, value in fields.items():
            setattr(job, name, value)
        db.commit()
        return job


def start_job(job_id: str, attempt: int) -> Job | None:
    """Mark a job as being worked on. None if it doesn't exist or is already done."""
    with session() as db:
        job = db.get(Job, job_id)
        if job is None or job.status == "done":
            return None
        job.status, job.attempts, job.error = "processing", attempt, None
        job.started_at, job.finished_at = utc_now(), None
        db.commit()
        return job


def finish_job(job_id: str, result: dict) -> None:
    update_job(job_id, status="done", result=result, document_id=result.get("document_id"),
               error=None, finished_at=utc_now())


def fail_job(job_id: str, error: str) -> None:
    update_job(job_id, status="failed", error=error, finished_at=utc_now())


def find_active_job(user_id: str | None = None, **filters) -> Job | None:
    """A queued or running job with these values (e.g. type="ingest", sha256=...)."""
    with session() as db:
        query = select(Job).where(Job.status.in_(ACTIVE))
        if user_id is not None:
            query = query.where(Job.user_id == user_id)
        for name, value in filters.items():
            query = query.where(getattr(Job, name) == value)
        return db.scalar(query.order_by(Job.created_at.desc()).limit(1))
