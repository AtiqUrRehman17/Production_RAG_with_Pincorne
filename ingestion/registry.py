"""The record of every ingested document, kept in the app database (documents table).

Used to detect duplicate uploads (same user + same file hash) and to list
or delete a user's documents. The CLI, the API and the worker all share it.

Documents recorded by the earlier JSON registry (DOCUMENT_REGISTRY_PATH) are
imported once; the file is then renamed to <name>.imported and kept as a backup.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from database.engine import session
from database.models import Document
from utils.config import Settings
from utils.logger import get_logger

logger = get_logger(__name__)
_imported = False


@dataclass
class DocumentRecord:
    document_id: str
    user_id: str
    file_name: str
    file_type: str
    sha256: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    stored_path: str
    created_at: str


def _to_record(row: Document) -> DocumentRecord:
    return DocumentRecord(
        document_id=row.document_id, user_id=row.user_id, file_name=row.file_name,
        file_type=row.file_type, sha256=row.sha256, size_bytes=row.size_bytes,
        page_count=row.page_count, chunk_count=row.chunk_count, stored_path=row.stored_path,
        created_at=row.created_at.isoformat(timespec="seconds"),
    )


def _to_row(record: DocumentRecord) -> Document:
    fields = asdict(record)
    fields["created_at"] = datetime.fromisoformat(record.created_at)
    return Document(**fields)


def _import_json_registry(path: Path) -> None:
    """Move the documents of the old JSON registry into the database (once)."""
    global _imported
    _imported = True
    if not path.is_file():
        return
    records = json.loads(path.read_text(encoding="utf-8"))
    with session() as db:
        for record in records.values():
            db.merge(_to_row(DocumentRecord(**record)))
        db.commit()
    try:
        path.rename(path.with_name(path.name + ".imported"))
    except OSError:
        pass  # another process (API / worker) imported it at the same moment
    logger.info("Imported %d document(s) from %s into the database", len(records), path.name)


class DocumentRegistry:
    def __init__(self, settings: Settings):
        if not _imported:
            _import_json_registry(settings.document_registry_path)

    def get(self, document_id: str) -> DocumentRecord | None:
        with session() as db:
            row = db.get(Document, document_id)
            return _to_record(row) if row else None

    def find_by_hash(self, user_id: str, sha256: str) -> DocumentRecord | None:
        with session() as db:
            row = db.scalar(select(Document).where(Document.user_id == user_id, Document.sha256 == sha256))
            return _to_record(row) if row else None

    def list_for_user(self, user_id: str) -> list[DocumentRecord]:
        with session() as db:
            rows = db.scalars(select(Document).where(Document.user_id == user_id).order_by(Document.created_at))
            return [_to_record(row) for row in rows]

    def add(self, record: DocumentRecord) -> None:
        with session() as db:
            # merge: the same file ingested twice at once has the same ID, so it simply stays one record
            db.merge(_to_row(record))
            db.commit()
        logger.info("Registered document %s (%s)", record.document_id, record.file_name)

    def remove(self, document_id: str) -> None:
        with session() as db:
            row = db.get(Document, document_id)
            if row is not None:
                db.delete(row)
                db.commit()
                logger.info("Removed document %s from registry", document_id)
