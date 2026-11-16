"""Receive an uploaded file: save it where the worker will find it, then run the quick checks.

The quick checks (file type, size, corrupted / password-protected, duplicate)
run before the reply, so the user hears about a bad file at once. The slow part
(chunking, embedding, storing) is left to the worker.
"""

import asyncio
import re
import shutil
from pathlib import Path

from fastapi import UploadFile

from api.errors import APIError
from ingestion.registry import DocumentRegistry
from ingestion.validator import ValidatedFile, validate_file
from utils.config import Settings
from utils.exceptions import DuplicateDocumentError
from workers.jobs import find_active_job

_READ_BYTES = 1024 * 1024
# Characters Windows doesn't allow in file names, and control characters
_UNSAFE_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_STEM_CHARS = 150


def safe_file_name(name: str | None) -> str:
    """The uploaded file's name without any folder part or unsafe characters."""
    name = Path((name or "").replace("\\", "/")).name
    name = _UNSAFE_CHARACTERS.sub("_", name).strip(" .")
    stem, dot, extension = name.rpartition(".")
    if not dot or not stem or not extension:
        raise APIError(400, "invalid_file", "The file needs a name with an extension, e.g. report.pdf.")
    return f"{stem[:_MAX_STEM_CHARS]}.{extension}"


async def save_upload(upload: UploadFile, folder: Path, settings: Settings) -> Path:
    """Write the upload to `folder`, stopping as soon as it is over the size limit."""
    path = folder / safe_file_name(upload.filename)
    folder.mkdir(parents=True, exist_ok=True)
    size = 0
    with path.open("wb") as out:
        while chunk := await upload.read(_READ_BYTES):
            size += len(chunk)
            if size > settings.max_file_size_bytes:
                break
            out.write(chunk)
    if size > settings.max_file_size_bytes:
        shutil.rmtree(folder, ignore_errors=True)
        raise APIError(413, "file_too_large", f"The file is larger than the {settings.max_file_size_mb:g} MB limit.")
    return path


async def check_upload(path: Path, user_id: str, settings: Settings) -> ValidatedFile:
    """Validate the saved file and make sure it isn't uploaded (or being uploaded) already."""
    file = await asyncio.to_thread(validate_file, path, settings)
    existing = await asyncio.to_thread(DocumentRegistry(settings).find_by_hash, user_id, file.sha256)
    if existing:
        raise DuplicateDocumentError(f"This file was already uploaded as '{existing.file_name}'.",
                                     existing_document_id=existing.document_id)
    active = find_active_job(user_id, type="ingest", sha256=file.sha256)
    if active:
        raise APIError(409, "upload_in_progress", "This file is already being processed.",
                       details={"job_id": active.id})
    return file
