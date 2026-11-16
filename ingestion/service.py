"""Ingestion entry points.

prepare_document: validate -> check duplicate -> load -> clean -> tag metadata -> chunk
ingest_document:  prepare -> store vectors in Pinecone -> keep a copy of the file -> register
delete_document:  remove vectors, stored file and registry record

Kept as plain functions (no CLI or HTTP code) so the same code can later be
called from the API or from a background worker.
"""

import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from chunking.splitter import DocumentChunker
from ingestion.cleaning import clean_documents
from ingestion.loaders import load_file
from ingestion.registry import DocumentRecord, DocumentRegistry
from ingestion.validator import ValidatedFile, validate_file
from utils.config import Settings
from utils.exceptions import (
    DocumentLoadError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    FileValidationError,
)
from utils.logger import get_logger
from utils.tracing import traced
from vectordb.pinecone_store import get_store

logger = get_logger(__name__)

# Fixed namespace so the same user + same file always gets the same document_id
_DOCUMENT_ID_NAMESPACE = uuid.UUID("6f1c2a4e-3b7d-4e8a-9c5f-1d2e3f4a5b6c")
# User IDs become Pinecone namespaces and folder names, so keep them simple
_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


# ---------------------------------------------------------------- tracing
# Each ingestion step is a named step in LangSmith traces. Traces show counts and
# sizes rather than whole documents, and never the settings (they hold API keys).
def _if_done(summary):
    """A failed step has no result; its trace then shows the error instead."""
    return lambda result: summary(result) if result is not None else {}


def _text_summary(documents: list[Document]) -> dict:
    return {"documents": len(documents), "characters": sum(len(d.page_content) for d in documents)}


def _chunk_summary(chunks: list[Document]) -> dict:
    tokens = [c.metadata.get("token_count", 0) for c in chunks]
    return {
        "chunks": len(chunks),
        "tokens_min": min(tokens, default=0),
        "tokens_max": max(tokens, default=0),
        "sections": [c.metadata.get("section", "") for c in chunks],
    }


_validate = traced(
    name="validate", process_inputs=lambda i: {"file": Path(i["path"]).name},
    process_outputs=_if_done(lambda f: {"file_type": f.file_type, "size_bytes": f.size_bytes,
                                        "page_count": f.page_count, "encoding": f.encoding}),
)(validate_file)
_load = traced(
    name="load", process_inputs=lambda i: {"file": i["file"].file_name}, process_outputs=_if_done(_text_summary),
)(load_file)
_clean = traced(
    name="clean", process_inputs=lambda i: _text_summary(i["documents"]), process_outputs=_if_done(_text_summary),
)(clean_documents)


@traced(name="chunk", process_inputs=lambda i: _text_summary(i["documents"]), process_outputs=_if_done(_chunk_summary))
def _chunk(documents: list[Document], settings: Settings) -> list[Document]:
    return DocumentChunker(settings).split(documents)


@traced(name="embed_and_store", process_inputs=lambda i: {"chunks": len(i["chunks"]), "namespace": i["namespace"]},
        process_outputs=_if_done(lambda n: {"stored": n}))
def _store_chunks(chunks: list[Document], namespace: str) -> int:
    # Embedding happens inside: the vector store embeds the chunks, then saves them
    return get_store().add_chunks(chunks, namespace=namespace)


@dataclass
class PreparedDocument:
    document_id: str
    user_id: str
    file: ValidatedFile
    documents: list[Document]  # cleaned pages/sections as loaded
    chunks: list[Document]  # ready to embed

    @property
    def total_chars(self) -> int:
        return sum(len(d.page_content) for d in self.documents)


def make_document_id(user_id: str, sha256: str) -> str:
    return str(uuid.uuid5(_DOCUMENT_ID_NAMESPACE, f"{user_id}:{sha256}"))


def check_user_id(user_id: str) -> None:
    if not _USER_ID_PATTERN.match(user_id):
        raise FileValidationError(
            "User ID may only contain letters, numbers, '-' and '_' (max 64 characters)."
        )


@traced(name="prepare", process_inputs=lambda i: {"file": Path(i["path"]).name, "user_id": i["user_id"]},
        process_outputs=_if_done(lambda p: {"document_id": p.document_id, "chunks": len(p.chunks)}))
def prepare_document(path: Path, user_id: str, settings: Settings) -> PreparedDocument:
    check_user_id(user_id)
    file = _validate(path, settings)

    registry = DocumentRegistry(settings)
    existing = registry.find_by_hash(user_id, file.sha256)
    if existing:
        raise DuplicateDocumentError(
            f"This file was already uploaded as '{existing.file_name}'.",
            existing_document_id=existing.document_id,
        )

    documents = _clean(_load(file), file.file_type)
    if not documents:
        raise DocumentLoadError(f"No readable text was found in {file.file_name}.")

    document_id = make_document_id(user_id, file.sha256)
    for doc in documents:
        # Replace loader-specific metadata with our own consistent set
        page_number = doc.metadata.get("page_number")
        doc.metadata = {
            "document_id": document_id,
            "user_id": user_id,
            "file_name": file.file_name,
            "file_type": file.file_type,
        }
        if page_number is not None:
            doc.metadata["page_number"] = page_number

    chunks = _chunk(documents, settings)
    prepared = PreparedDocument(
        document_id=document_id, user_id=user_id, file=file, documents=documents, chunks=chunks
    )
    logger.info(
        "Prepared %s: %d section(s), %d characters, %d chunks",
        file.file_name, len(documents), prepared.total_chars, len(chunks),
    )
    return prepared


@traced(name="ingest", process_inputs=lambda i: {"file": Path(i["path"]).name, "user_id": i["user_id"]},
        process_outputs=_if_done(lambda r: {"document_id": r.document_id, "file_name": r.file_name,
                                            "chunks": r.chunk_count, "pages": r.page_count}))
def ingest_document(path: Path, user_id: str, settings: Settings) -> DocumentRecord:
    """Fully ingest a file. If any step fails, the steps already done are undone,
    so a document is either completely stored or not stored at all."""
    prepared = prepare_document(path, user_id, settings)
    file = prepared.file
    store = get_store()
    stored_path = settings.upload_dir / user_id / f"{prepared.document_id}.{file.file_type}"

    # Clear vectors left behind by an earlier ingest of this file that crashed midway
    store.delete_document(prepared.document_id, namespace=user_id)
    try:
        _store_chunks(prepared.chunks, namespace=user_id)

        stored_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file.path, stored_path)

        record = DocumentRecord(
            document_id=prepared.document_id,
            user_id=user_id,
            file_name=file.file_name,
            file_type=file.file_type,
            sha256=file.sha256,
            size_bytes=file.size_bytes,
            page_count=file.page_count,
            chunk_count=len(prepared.chunks),
            stored_path=str(stored_path),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        DocumentRegistry(settings).add(record)
    except BaseException:
        logger.warning("Ingestion of %s failed, rolling back", file.file_name)
        chunk_ids = [chunk.metadata["chunk_id"] for chunk in prepared.chunks]
        _rollback(prepared.document_id, user_id, stored_path, chunk_ids)
        raise

    logger.info("Ingested %s as %s", file.file_name, prepared.document_id)
    return record


def _rollback(document_id: str, user_id: str, stored_path: Path, chunk_ids: list[str]) -> None:
    # Best effort: log cleanup problems but let the original error surface
    try:
        get_store().delete_document(document_id, namespace=user_id, known_ids=chunk_ids)
    except Exception:
        logger.exception("Rollback: could not delete vectors of %s", document_id)
    stored_path.unlink(missing_ok=True)


def list_documents(user_id: str, settings: Settings) -> list[DocumentRecord]:
    return DocumentRegistry(settings).list_for_user(user_id)


def delete_document(document_id: str, user_id: str, settings: Settings) -> DocumentRecord:
    registry = DocumentRegistry(settings)
    record = registry.get(document_id)
    # Treat another user's document as not found, so IDs can't be probed
    if record is None or record.user_id != user_id:
        raise DocumentNotFoundError(f"No document with ID {document_id} was found.")

    # Vectors first: if this fails the record stays, so the delete can be retried
    known_ids = [f"{document_id}:{i}" for i in range(record.chunk_count)]
    get_store().delete_document(document_id, namespace=user_id, known_ids=known_ids)
    Path(record.stored_path).unlink(missing_ok=True)
    registry.remove(document_id)
    logger.info("Deleted document %s (%s)", document_id, record.file_name)
    return record
