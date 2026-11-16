"""Upload, list and delete documents. Uploads and deletes run in the background worker."""

import shutil

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import JobQueue, current_user_id, get_db, get_queue
from api.errors import APIError
from api.pagination import MAX_LIMIT, paginate
from api.schemas.common import Page
from api.schemas.documents import DocumentOut, JobOut
from api.services.uploads import check_upload, save_upload
from database.models import Document, new_id
from utils.config import get_settings
from utils.request_context import current_request_id
from workers import jobs, queue

router = APIRouter(prefix="/documents", tags=["documents"])

# Room for the multipart wrapping around the file itself
_UPLOAD_OVERHEAD_BYTES = 1024 * 1024


def _get_document(db: Session, document_id: str, user_id: str) -> Document:
    document = db.get(Document, document_id)
    # Another user's document is "not found", so IDs can't be probed
    if document is None or document.user_id != user_id:
        raise APIError(404, "document_not_found", f"No document with ID {document_id} was found.")
    return document


@router.post("", response_model=JobOut, status_code=202,
             summary="Upload a PDF, DOCX or TXT file",
             description="Quick checks run at once (type, size, corrupted, password, duplicate); "
                         "then a background job ingests the file. Follow it with GET /jobs/{id}.")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(current_user_id),
    job_queue: JobQueue = Depends(get_queue),
) -> JobOut:
    settings = get_settings()
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > settings.max_file_size_bytes + _UPLOAD_OVERHEAD_BYTES:
        raise APIError(413, "file_too_large", f"The file is larger than the {settings.max_file_size_mb:g} MB limit.")
    await job_queue.connection()  # fail before receiving the file if the queue is down

    job_id = new_id()
    folder = settings.incoming_dir / job_id
    path = await save_upload(file, folder, settings)
    try:
        validated = await check_upload(path, user_id, settings)
        job = jobs.create_job("ingest", user_id, id=job_id, request_id=current_request_id(),
                              file_name=validated.file_name, sha256=validated.sha256, params={"path": str(path)})
        await job_queue.enqueue(queue.INGEST, job.id, job_id=job.id)
    except BaseException as exc:
        shutil.rmtree(folder, ignore_errors=True)
        if jobs.get_job(job_id):
            jobs.fail_job(job_id, str(getattr(exc, "message", exc)))
        raise
    return JobOut.model_validate(job)


@router.get("", response_model=Page[DocumentOut], summary="Your documents, newest first")
def list_documents(
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(get_db),
) -> Page[DocumentOut]:
    query = select(Document).where(Document.user_id == user_id)
    rows, next_cursor = paginate(db, query, Document.created_at, Document.document_id, limit, cursor)
    return Page(items=[DocumentOut.model_validate(row) for row in rows], next_cursor=next_cursor)


@router.get("/{document_id}", response_model=DocumentOut, summary="One document")
def get_document(document_id: str, user_id: str = Depends(current_user_id),
                 db: Session = Depends(get_db)) -> DocumentOut:
    return DocumentOut.model_validate(_get_document(db, document_id, user_id))


@router.delete("/{document_id}", response_model=JobOut, status_code=202,
               summary="Delete a document and its chunks (background job)")
async def delete_document(
    document_id: str,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(get_db),
    job_queue: JobQueue = Depends(get_queue),
) -> JobOut:
    document = _get_document(db, document_id, user_id)
    active = jobs.find_active_job(user_id, type="delete", document_id=document_id)
    if active:
        return JobOut.model_validate(active)  # already being deleted
    job = jobs.create_job("delete", user_id, request_id=current_request_id(), file_name=document.file_name,
                          document_id=document_id)
    try:
        await job_queue.enqueue(queue.DELETE, job.id, job_id=job.id)
    except APIError as exc:
        jobs.fail_job(job.id, exc.message)
        raise
    return JobOut.model_validate(job)
