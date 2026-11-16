"""Progress of background work (uploads, deletes, moving data to a new account)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import current_user_id, get_db
from api.errors import APIError
from api.pagination import MAX_LIMIT, paginate
from api.schemas.common import Page
from api.schemas.documents import JobOut
from database.models import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])

JobStatus = Literal["queued", "processing", "done", "failed"]
JobType = Literal["ingest", "delete", "evaluation", "transfer"]


def list_jobs_page(db: Session, limit: int, cursor: str | None, status: list[str] | None,
                   job_type: str | None, user_id: str | None) -> Page[JobOut]:
    query = select(Job)
    if user_id is not None:
        query = query.where(Job.user_id == user_id)
    if status:
        query = query.where(Job.status.in_(status))
    if job_type:
        query = query.where(Job.type == job_type)
    rows, next_cursor = paginate(db, query, Job.created_at, Job.id, limit, cursor)
    return Page(items=[JobOut.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.get("", response_model=Page[JobOut], summary="Your recent jobs, newest first")
def list_jobs(
    status: list[JobStatus] | None = Query(None, description="Repeat for several, e.g. ?status=queued&status=processing"),
    type: JobType | None = None,
    limit: int = Query(20, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(get_db),
) -> Page[JobOut]:
    return list_jobs_page(db, limit, cursor, status, type, user_id)


@router.get("/{job_id}", response_model=JobOut, summary="One job: queued -> processing -> done / failed")
def get_job(job_id: str, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise APIError(404, "job_not_found", f"No job with ID {job_id} was found.")
    return JobOut.model_validate(job)
