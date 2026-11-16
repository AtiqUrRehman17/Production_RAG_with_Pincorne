from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    file_name: str
    file_type: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    created_at: datetime


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: Literal["ingest", "delete", "evaluation", "transfer"]
    status: Literal["queued", "processing", "done", "failed"]
    file_name: str | None
    document_id: str | None
    progress: dict | None  # {"step": "questions", "done": 3, "total": 45} (evaluations)
    result: dict | None
    error: str | None
    attempts: int
    request_id: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
