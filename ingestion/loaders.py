"""Loaders that turn a validated file into LangChain Documents.

All loaders produce Markdown-style text (headings as '#', tables as Markdown
tables) so the chunker can split every file type along its structure.

  PDF  -> one Document per page (keeps page numbers for citations)
  DOCX -> one Document for the whole file (Word files have no fixed pages)
  TXT  -> one Document for the whole file
"""

from collections.abc import Iterator

import docx
from docx.document import Document as DocxDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_community.document_loaders import TextLoader
from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from langchain_pymupdf4llm import PyMuPDF4LLMLoader

from ingestion.validator import ValidatedFile
from utils.exceptions import DocumentLoadError
from utils.logger import get_logger

logger = get_logger(__name__)


class DocxMarkdownLoader(BaseLoader):
    """Loads a .docx file as Markdown, keeping headings, lists and tables in order."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def lazy_load(self) -> Iterator[Document]:
        document = docx.Document(self.file_path)
        blocks = [block for block in self._iter_blocks(document) if block]
        yield Document(page_content="\n\n".join(blocks), metadata={"source": self.file_path})

    def _iter_blocks(self, document: DocxDocument) -> Iterator[str]:
        # iter_inner_content() yields paragraphs and tables in document order
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                yield self._paragraph_to_markdown(item)
            elif isinstance(item, Table):
                yield self._table_to_markdown(item)

    @staticmethod
    def _paragraph_to_markdown(paragraph: Paragraph) -> str:
        text = paragraph.text.strip()
        if not text:
            return ""
        style = (paragraph.style.name if paragraph.style is not None else "").lower()
        if style == "title":
            return f"# {text}"
        if style.startswith("heading"):
            level = style.removeprefix("heading").strip()
            depth = int(level) if level.isdigit() else 1
            return f"{'#' * min(depth, 6)} {text}"
        if "list" in style:
            return f"- {text}"
        return text

    @staticmethod
    def _table_to_markdown(table: Table) -> str:
        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ").replace("|", "\\|") for cell in row.cells]
            rows.append(cells)
        rows = [r for r in rows if any(r)]
        if not rows:
            return ""

        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * width]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)


def _load_pdf(file: ValidatedFile) -> list[Document]:
    loader = PyMuPDF4LLMLoader(str(file.path), mode="page")
    documents = loader.load()
    for index, doc in enumerate(documents):
        # Our own 1-based page number, used for citations like "page 12"
        doc.metadata["page_number"] = index + 1
    return documents


def _load_docx(file: ValidatedFile) -> list[Document]:
    return DocxMarkdownLoader(str(file.path)).load()


def _load_txt(file: ValidatedFile) -> list[Document]:
    return TextLoader(str(file.path), encoding=file.encoding).load()


_LOADERS = {
    "pdf": _load_pdf,
    "docx": _load_docx,
    "txt": _load_txt,
}


def load_file(file: ValidatedFile) -> list[Document]:
    try:
        documents = _LOADERS[file.file_type](file)
    except Exception as exc:
        logger.exception("Failed to load %s", file.file_name)
        raise DocumentLoadError(f"Could not extract text from {file.file_name}.") from exc

    logger.info("Loaded %s into %d document(s)", file.file_name, len(documents))
    return documents
