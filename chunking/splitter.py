"""Structure-aware chunking built on LangChain text splitters.

Steps:
  1. Split each page/document by Markdown headings (h1-h3). For PDFs the current
     heading is carried across page breaks, so text continuing on the next page
     still knows which section it belongs to.
  2. Split sections longer than CHUNK_SIZE tokens at deeper headings, then
     paragraphs, lines, sentences and finally words, with CHUNK_OVERLAP tokens
     of overlap.
  3. Merge small neighbours: a heading-only piece joins the section after it, a
     tiny intro joins the sub-section below it, and a section continuing over a
     page break is joined back together.
  4. Prefix each chunk with its document name and section path, which makes
     chunks much easier to find in search.
"""

import re
from dataclasses import dataclass, field

from langchain_core.documents import Document
from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    Language,
    RecursiveCharacterTextSplitter,
)

from utils.config import Settings
from utils.logger import get_logger
from utils.tokens import TOKEN_ENCODING, count_tokens

logger = get_logger(__name__)

_HEADER_LEVELS = [("#", "h1"), ("##", "h2"), ("###", "h3")]
_HEADER_KEYS = [key for _, key in _HEADER_LEVELS]
_MARKDOWN_EMPHASIS = re.compile(r"[*_`]+")
# LangChain's Markdown separators (headings, code, rules, paragraphs, lines, words),
# plus sentence ends before falling back to splitting between words
_MARKDOWN_SEPARATORS = RecursiveCharacterTextSplitter.get_separators_for_language(Language.MARKDOWN)
_SENTENCE_END = r"(?<=[.!?])\s+"
_SEPARATORS = _MARKDOWN_SEPARATORS[:-2] + [_SENTENCE_END] + _MARKDOWN_SEPARATORS[-2:]


@dataclass
class _Section:
    text: str
    headers: dict[str, str]
    page_start: int | None
    page_end: int | None
    tokens: int = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = count_tokens(self.text)

    @property
    def is_heading_only(self) -> bool:
        return all(line.lstrip().startswith("#") for line in self.text.splitlines() if line.strip())


class DocumentChunker:
    def __init__(self, settings: Settings):
        self.chunk_size = settings.chunk_size
        self.min_chunk_size = settings.min_chunk_size
        self._header_splitter = ExperimentalMarkdownSyntaxTextSplitter(
            headers_to_split_on=_HEADER_LEVELS, strip_headers=False
        )
        self._size_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=TOKEN_ENCODING,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=_SEPARATORS,
            is_separator_regex=True,  # the Markdown separators are regex patterns
        )

    def split(self, documents: list[Document]) -> list[Document]:
        """Turn the loaded documents of ONE file into chunks."""
        if not documents:
            return []

        sections = self._split_by_headers(documents)
        sections = self._split_oversized(sections)
        sections = self._merge_small(sections)
        chunks = self._to_chunks(sections, documents[0].metadata)

        logger.info(
            "Chunked %s into %d chunks", documents[0].metadata.get("file_name"), len(chunks)
        )
        return chunks

    def _split_by_headers(self, documents: list[Document]) -> list[_Section]:
        sections: list[_Section] = []
        carried: dict[str, str] = {}

        for doc in documents:
            page = doc.metadata.get("page_number")
            for split in self._header_splitter.split_text(doc.page_content):
                text = split.page_content.strip()
                if not text:
                    continue
                headers = self._resolve_headers(split.metadata, carried)
                sections.append(_Section(text, headers, page, page))
                carried = headers
        return sections

    @staticmethod
    def _resolve_headers(found: dict[str, str], carried: dict[str, str]) -> dict[str, str]:
        """Combine headings found in this piece with the ones carried from before.

        A piece starting with '## B' after '# A' becomes A > B. A piece with no
        heading (e.g. the top of a new PDF page) keeps the previous headings.
        """
        found = {k: v for k, v in found.items() if k in _HEADER_KEYS}
        if not found:
            return dict(carried)

        top_level = min(_HEADER_KEYS.index(k) for k in found)
        parents = {k: carried[k] for k in _HEADER_KEYS[:top_level] if k in carried}
        return {**parents, **found}

    def _split_oversized(self, sections: list[_Section]) -> list[_Section]:
        result: list[_Section] = []
        for section in sections:
            if section.tokens <= self.chunk_size:
                result.append(section)
                continue
            for piece in self._size_splitter.split_text(section.text):
                result.append(
                    _Section(piece, section.headers, section.page_start, section.page_end)
                )
        return result

    def _merge_small(self, sections: list[_Section]) -> list[_Section]:
        if not sections:
            return []

        merged = [sections[0]]
        for section in sections[1:]:
            current = merged[-1]
            if self._can_merge(current, section):
                merged[-1] = _Section(
                    f"{current.text}\n\n{section.text}",
                    section.headers,
                    current.page_start,
                    section.page_end,
                )
            else:
                merged.append(section)
        # A heading left over at the very end has no content to search for
        return [s for s in merged if not s.is_heading_only]

    def _can_merge(self, current: _Section, following: _Section) -> bool:
        # The +2 accounts for the blank line joining the two pieces
        if current.tokens + following.tokens + 2 > self.chunk_size:
            return False
        # Same section, split by a page break or a code block
        if following.headers == current.headers:
            return True
        # A heading with no text of its own (e.g. the document title) belongs with what follows
        if current.is_heading_only:
            return True
        # A tiny piece (usually just a heading) that introduces the section below it
        is_parent = current.headers.items() <= following.headers.items()
        return current.tokens < self.min_chunk_size and is_parent

    @staticmethod
    def _section_path(headers: dict[str, str]) -> str:
        titles = [_MARKDOWN_EMPHASIS.sub("", headers[k]).strip() for k in _HEADER_KEYS if k in headers]
        return " > ".join(t for t in titles if t)

    def _to_chunks(self, sections: list[_Section], base_metadata: dict) -> list[Document]:
        document_id = base_metadata["document_id"]
        file_name = base_metadata["file_name"]
        common = {
            k: base_metadata[k] for k in ("document_id", "user_id", "file_name", "file_type")
        }

        chunks = []
        for index, section in enumerate(sections):
            section_path = self._section_path(section.headers)
            context = f"Document: {file_name}"
            if section_path:
                context += f"\nSection: {section_path}"

            metadata = {
                **common,
                "chunk_id": f"{document_id}:{index}",
                "chunk_index": index,
                "section": section_path,
                "token_count": section.tokens,
            }
            if section.page_start is not None:
                metadata["page_number"] = section.page_start
                metadata["page_end"] = section.page_end

            chunks.append(Document(page_content=f"{context}\n\n{section.text}", metadata=metadata))
        return chunks
