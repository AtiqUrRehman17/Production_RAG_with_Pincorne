"""Text cleaning applied to every loaded document before chunking."""

import re
import unicodedata
from collections import Counter

from langchain_core.documents import Document

# Control characters except tab (\x09) and newline (\x0a)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
# A word split across lines by a hyphen: "informa-\ntion"
_HYPHEN_LINE_BREAK = re.compile(r"(\w)-\n(\w)")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")
_MANY_BLANK_LINES = re.compile(r"\n{3,}")

# Header/footer detection for multi-page PDFs
_EDGE_LINES = 2  # how many lines at the top and bottom of a page to inspect
_MIN_PAGES_FOR_EDGE_CHECK = 3
_EDGE_REPEAT_RATIO = 0.5  # line must repeat on at least half the pages
_MAX_EDGE_LINE_CHARS = 80  # headers/footers are short; longer lines are body text


def clean_text(text: str) -> str:
    # NFKC turns ligatures and odd forms into plain characters ("ﬁ" -> "fi")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = _HYPHEN_LINE_BREAK.sub(r"\1\2", text)
    text = _TRAILING_SPACES.sub("\n", text)
    text = _MANY_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _edge_key(line: str) -> str | None:
    """Key used to compare possible header/footer lines across pages, or None if
    the line can't be one (too long, or a Markdown heading, which is real content)."""
    line = line.strip()
    if not line or line.startswith("#") or len(line) > _MAX_EDGE_LINE_CHARS:
        return None
    # "Page 3 of 10" and "Page 4 of 10" should count as the same footer
    return re.sub(r"\d+", "#", line.lower())


def _edge_indexes(lines: list[str]) -> set[int]:
    non_empty = [i for i, l in enumerate(lines) if l.strip()]
    return set(non_empty[:_EDGE_LINES] + non_empty[-_EDGE_LINES:])


def remove_repeated_edges(pages: list[Document]) -> list[Document]:
    """Remove headers/footers that repeat at the top or bottom of most pages."""
    if len(pages) < _MIN_PAGES_FOR_EDGE_CHECK:
        return pages

    counts: Counter[str] = Counter()
    for page in pages:
        lines = page.page_content.split("\n")
        keys = {_edge_key(lines[i]) for i in _edge_indexes(lines)}
        counts.update(k for k in keys if k)

    threshold = len(pages) * _EDGE_REPEAT_RATIO
    repeated = {key for key, n in counts.items() if n >= threshold}
    if not repeated:
        return pages

    for page in pages:
        lines = page.page_content.split("\n")
        edges = _edge_indexes(lines)
        page.page_content = "\n".join(
            l for i, l in enumerate(lines) if not (i in edges and _edge_key(l) in repeated)
        )
    return pages


def clean_documents(documents: list[Document], file_type: str) -> list[Document]:
    if file_type == "pdf":
        documents = remove_repeated_edges(documents)
    for doc in documents:
        doc.page_content = clean_text(doc.page_content)
    # Blank pages (e.g. intentionally empty pages in a PDF) add nothing
    return [doc for doc in documents if doc.page_content]
