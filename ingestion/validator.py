"""File validation: runs before any parsing so bad files are rejected early.

Checks, in order:
  1. The file exists and has an allowed extension
  2. It is not empty and not larger than the size limit
  3. The file's real content matches its extension (checked from its bytes)
  4. Type-specific checks: corrupted, password-protected, too many pages,
     scanned PDF with no text (no OCR yet), empty document
"""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import docx
import pymupdf
from charset_normalizer import from_bytes

from utils.config import Settings
from utils.exceptions import FileValidationError
from utils.hashing import sha256_file
from utils.logger import get_logger

logger = get_logger(__name__)

_PDF_SIGNATURE = b"%PDF-"
_ZIP_SIGNATURE = b"PK\x03\x04"
# Password-protected .docx files and old .doc files use this container format
_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
# Detectors can't reliably tell similar legacy code pages apart, so prefer the most
# common one (Windows Western) when it decodes almost as cleanly as the top guess
_PREFERRED_LEGACY_ENCODING = "cp1252"
_LEGACY_CHAOS_MARGIN = 0.05


@dataclass(frozen=True)
class ValidatedFile:
    path: Path
    file_name: str
    file_type: str  # "pdf" | "docx" | "txt"
    size_bytes: int
    sha256: str
    page_count: int | None = None  # PDFs only
    encoding: str | None = None  # TXT only


def validate_file(path: Path, settings: Settings) -> ValidatedFile:
    path = Path(path)
    if not path.is_file():
        raise FileValidationError(f"File not found: {path}")

    file_type = path.suffix.lower().lstrip(".")
    allowed = settings.allowed_extension_set
    if file_type not in allowed:
        raise FileValidationError(
            f"Unsupported file type '.{file_type}'. Allowed: {', '.join(sorted(allowed))}"
        )

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise FileValidationError("The file is empty.")
    if size_bytes > settings.max_file_size_bytes:
        raise FileValidationError(
            f"File is {size_bytes / 1024 / 1024:.1f} MB. "
            f"The limit is {settings.max_file_size_mb:g} MB."
        )

    page_count = None
    encoding = None
    if file_type == "pdf":
        page_count = _validate_pdf(path, settings)
    elif file_type == "docx":
        _validate_docx(path)
    elif file_type == "txt":
        encoding = _validate_txt(path)

    validated = ValidatedFile(
        path=path,
        file_name=path.name,
        file_type=file_type,
        size_bytes=size_bytes,
        sha256=sha256_file(path),
        page_count=page_count,
        encoding=encoding,
    )
    logger.info("Validated %s (%s, %d bytes)", validated.file_name, file_type, size_bytes)
    return validated


def _read_head(path: Path, n: int = 1024) -> bytes:
    with path.open("rb") as f:
        return f.read(n)


def _validate_pdf(path: Path, settings: Settings) -> int:
    # The PDF spec allows a little junk before the signature, so search the first 1 KB
    if _PDF_SIGNATURE not in _read_head(path):
        raise FileValidationError("This file has a .pdf extension but is not a real PDF.")

    try:
        pdf = pymupdf.open(path)
    except Exception as exc:
        raise FileValidationError("The PDF is corrupted and cannot be opened.") from exc

    with pdf:
        if pdf.needs_pass:
            raise FileValidationError(
                "The PDF is password-protected. Please remove the password and upload again."
            )

        page_count = pdf.page_count
        if page_count == 0:
            raise FileValidationError("The PDF has no pages.")
        if page_count > settings.max_pdf_pages:
            raise FileValidationError(
                f"The PDF has {page_count} pages. The limit is {settings.max_pdf_pages}."
            )

        # A scanned PDF is just images, so it has almost no extractable text
        try:
            total_chars = sum(len(page.get_text().strip()) for page in pdf)
        except Exception as exc:
            raise FileValidationError("The PDF is damaged and its text cannot be read.") from exc

    if total_chars / page_count < settings.min_text_chars_per_page:
        raise FileValidationError(
            "This PDF looks scanned (it has little or no selectable text). "
            "Scanned documents are not supported yet."
        )
    return page_count


def _validate_docx(path: Path) -> None:
    head = _read_head(path, 8)
    if head.startswith(_OLE_SIGNATURE):
        raise FileValidationError(
            "This file is either password-protected or an old .doc file. "
            "Please remove the password or save it as .docx and upload again."
        )
    if not head.startswith(_ZIP_SIGNATURE) or not zipfile.is_zipfile(path):
        raise FileValidationError("This file has a .docx extension but is not a real Word document.")

    try:
        with zipfile.ZipFile(path) as zf:
            if "word/document.xml" not in zf.namelist():
                raise FileValidationError("This file is not a valid Word document.")
        document = docx.Document(str(path))
    except FileValidationError:
        raise
    except Exception as exc:
        raise FileValidationError("The Word document is corrupted and cannot be opened.") from exc

    has_text = any(p.text.strip() for p in document.paragraphs) or any(
        cell.text.strip() for table in document.tables for row in table.rows for cell in row.cells
    )
    if not has_text:
        raise FileValidationError("The Word document has no text.")


def _validate_txt(path: Path) -> str:
    raw = path.read_bytes()

    # NUL bytes mean binary content, except in UTF-16 text where they are normal
    if not raw.startswith(_UTF16_BOMS) and b"\x00" in raw[:8192]:
        raise FileValidationError("This file has a .txt extension but contains binary data.")

    encoding, text = _detect_encoding(raw)
    if not text.strip():
        raise FileValidationError("The text file has no text.")
    return encoding


def _detect_encoding(raw: bytes) -> tuple[str, str]:
    # Most text files are UTF-8; "utf-8-sig" also handles an optional BOM
    try:
        return "utf-8-sig", raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    if raw.startswith(_UTF16_BOMS):
        try:
            return "utf-16", raw.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise FileValidationError("The text file's encoding could not be detected.") from exc

    matches = from_bytes(raw)
    best = matches.best()
    if best is None:
        raise FileValidationError("The text file's encoding could not be detected.")
    for match in matches:
        if (
            match.encoding == _PREFERRED_LEGACY_ENCODING
            and match.chaos <= best.chaos + _LEGACY_CHAOS_MARGIN
        ):
            return match.encoding, str(match)
    return best.encoding, str(best)
