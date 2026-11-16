"""LangChain retriever over the user's Pinecone namespace.

For a question it:
  1. searches only the user's own namespace (optionally only some documents),
     fetching RETRIEVAL_FETCH_K candidates when reranking is on, TOP_K otherwise
  2. stops early if even the best candidate scores below MIN_RELEVANCE_SCORE:
     the question is off-topic, so "the documents don't cover this" (and no
     rerank request is spent on it)
  3. with reranking: a reranker re-scores the candidates by reading the question
     and each chunk together; chunks below RERANK_MIN_SCORE are dropped and at
     most RERANK_TOP_N are kept. The reranker's #1 chunk only has to reach the
     lower RERANK_MIN_BEST_SCORE: its ranking is reliable even when unusual
     wording makes its absolute score low.
     without reranking (or if it fails): of the TOP_K best candidates, chunks
     more than RELATIVE_SCORE_MARGIN below the best one are dropped. Unrelated
     chunks of an on-topic document still score ~0.55-0.62, so the absolute
     threshold alone lets noise through.
     questions about a document as a whole ("what is this file about?",
     "summarize the document") skip step 3: no single chunk answers them, so the
     reranker scores every chunk near 0 and nothing would be kept. They get
     chunks spread over the whole document instead (its start always included)
  4. restores metadata types (Pinecone returns every number as a float)
  5. joins neighbouring chunks of the same section (pieces of one long section
     split with overlap) into one passage, removing the repeated overlap
"""

import re
from collections import defaultdict

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables.config import set_config_context

from retrieval.reranker import Reranker
from utils.config import Settings
from utils.exceptions import EmbeddingError, VectorStoreError
from utils.logger import get_logger
from vectordb.pinecone_store import TEXT_KEY, PineconeStore, get_store

logger = get_logger(__name__)

_INT_FIELDS = ("chunk_index", "page_number", "page_end", "token_count")
# Overlaps shorter than this are treated as coincidence, not real overlap
_MIN_OVERLAP_CHARS = 20

# Questions about a whole document. "About"/"summary" alone isn't enough ("what is
# crisis detection about?" is a normal question): the question must name the file
# ("this pdf", "the document") or be a short one about "it"/"this"
_OVERVIEW_ASK = re.compile(
    r"\b(summar(y|ies|i[sz]e\w*)|overview|gist|tl;?dr|main (points?|ideas?|topics?|themes?)"
    r"|key (points?|takeaways?|ideas?|topics?)|what\b.*\babout|what does\b.*\b(cover|contain|say|discuss|describe)"
    r"|talk(s|ing)? about|purpose of)\b",
    re.IGNORECASE,
)
_DOCUMENT_WORD = re.compile(r"\b(files?|documents?|docs?|pdfs?|docx|txt|uploads?|attachments?)\b", re.IGNORECASE)
_PRONOUN = re.compile(r"\b(it|this|that|these|those)\b", re.IGNORECASE)
_MAX_OVERVIEW_DOCUMENTS = 3


def is_overview_question(question: str) -> bool:
    if not _OVERVIEW_ASK.search(question):
        return False
    return bool(_DOCUMENT_WORD.search(question)) or (
        len(question.split()) <= 6 and bool(_PRONOUN.search(question))
    )


def _spread(items: list, count: int) -> list:
    """`count` items spread evenly from first to last (all if there are fewer)."""
    if len(items) <= count:
        return items
    if count == 1:
        return items[:1]
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def with_overrides(settings: Settings, no_rerank: bool = False, top_k: int | None = None) -> Settings:
    """Settings with per-request retrieval changes: no reranking (for comparison),
    or a different number of passages (top_k = most passages, with or without reranking)."""
    updates = {}
    if no_rerank:
        updates["reranker_enabled"] = False
    if top_k:
        updates.update(top_k=top_k, rerank_top_n=top_k,
                       retrieval_fetch_k=max(settings.retrieval_fetch_k, top_k))
    return settings.model_copy(update=updates) if updates else settings


class DocumentRetriever(BaseRetriever):
    store: PineconeStore
    user_id: str
    top_k: int = 5
    min_score: float = 0.55
    relative_margin: float = 0.1
    document_ids: list[str] | None = None  # None = search all of the user's documents
    reranker: Reranker | None = None  # None = embedding scores only
    fetch_k: int = 20
    rerank_top_n: int = 8
    rerank_min_score: float = 0.2
    rerank_min_best_score: float = 0.02

    @classmethod
    def for_user(
        cls, user_id: str, settings: Settings, document_ids: list[str] | None = None
    ) -> "DocumentRetriever":
        return cls(
            store=get_store(),
            user_id=user_id,
            top_k=settings.top_k,
            min_score=settings.min_relevance_score,
            relative_margin=settings.relative_score_margin,
            document_ids=document_ids or None,
            reranker=Reranker(settings) if settings.reranker_enabled else None,
            fetch_k=settings.retrieval_fetch_k,
            rerank_top_n=settings.rerank_top_n,
            rerank_min_score=settings.rerank_min_score,
            rerank_min_best_score=settings.rerank_min_best_score,
        )

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        search_filter = {"document_id": {"$in": self.document_ids}} if self.document_ids else None
        k = self.fetch_k if self.reranker else self.top_k
        try:
            results = self.store.vector_store.similarity_search_with_score(
                query, k=k, namespace=self.user_id, filter=search_filter
            )
        except EmbeddingError:
            raise  # already has a clear message
        except Exception as exc:
            raise VectorStoreError("Search in Pinecone failed.") from exc

        # Results come back best first
        best = max((score for _, score in results), default=0.0)
        if best < self.min_score:
            logger.info("Best score %.3f is below %.2f: off-topic for user '%s'",
                        best, self.min_score, self.user_id)
            return []

        if is_overview_question(query):
            chunks = self._overview(results, best)
            if chunks:
                return merge_adjacent(chunks)

        chunks = None
        if self.reranker:
            # Run inside this retriever's tracing context, so LangSmith shows the
            # rerank step under the retriever step instead of beside it
            with set_config_context({"callbacks": run_manager.get_child()}) as context:
                chunks = context.run(self._rerank, query, results)
        if chunks is None:
            chunks = self._filter_by_embedding_score(results[: self.top_k], best)
        return merge_adjacent(chunks)

    def _rerank(self, query: str, results: list[tuple[Document, float]]) -> list[Document] | None:
        """Keep the reranker's best chunks. None means reranking failed."""
        ranked = self.reranker.rerank(query, [doc for doc, _ in results])
        if ranked is None:
            logger.warning("Reranking unavailable; using embedding scores instead")
            return None

        embedding_scores = {id(doc): score for doc, score in results}
        # `ranked` is best first, so position 0 is the reranker's top choice
        kept = [
            (doc, score)
            for position, (doc, score) in enumerate(ranked)
            if score >= self.rerank_min_score
            or (position == 0 and score >= self.rerank_min_best_score)
        ]
        chunks = [
            _tag(doc, score, embedding_scores[id(doc)], "rerank")
            for doc, score in kept[: self.rerank_top_n]
        ]
        logger.info(
            "Reranked %d candidates: kept %d (min %.2f, best chunk min %.2f) for user '%s'",
            len(results), len(chunks), self.rerank_min_score, self.rerank_min_best_score,
            self.user_id,
        )
        return chunks

    def _overview(self, results: list[tuple[Document, float]], best: float) -> list[Document]:
        """Chunks spread over the best matching documents, for questions about a whole document.
        Empty if they can't be read (the normal steps run instead)."""
        best_by_document: dict[str, float] = {}
        for doc, score in results:  # best first, so the first score seen is a document's best
            best_by_document.setdefault(doc.metadata["document_id"], score)
        # The documents in scope, or the ones that match the question about as well as the best
        document_ids = [doc_id for doc_id, score in best_by_document.items()
                        if self.document_ids or score >= best - self.relative_margin]
        document_ids = document_ids[:_MAX_OVERVIEW_DOCUMENTS]
        budget = self.rerank_top_n if self.reranker else self.top_k
        per_document = max(2, budget // len(document_ids))

        embedding_scores = {doc.metadata["chunk_id"]: score for doc, score in results}
        chunks: list[Document] = []
        try:
            for document_id in document_ids:
                ids = self.store.list_chunk_ids(document_id, self.user_id)
                ids.sort(key=lambda chunk_id: int(chunk_id.rpartition(":")[2]))
                fetched = self.store.index.fetch(ids=_spread(ids, per_document), namespace=self.user_id)
                for vector in fetched.vectors.values():
                    metadata = dict(vector.metadata)
                    text = metadata.pop(TEXT_KEY, "")
                    # All chunks of a document share its best score, so they stay in document order
                    chunks.append(_tag(Document(page_content=text, metadata=metadata),
                                       best_by_document[document_id],
                                       embedding_scores.get(vector.id, best_by_document[document_id]),
                                       "overview"))
        except Exception:
            logger.warning("Could not read the documents' chunks for an overview question", exc_info=True)
            return []
        logger.info("Overview question: %d chunks from %d document(s) for user '%s'",
                    len(chunks), len(document_ids), self.user_id)
        return chunks

    def _filter_by_embedding_score(
        self, results: list[tuple[Document, float]], best: float
    ) -> list[Document]:
        cutoff = max(self.min_score, best - self.relative_margin)
        chunks = [_tag(doc, score, score, "embedding") for doc, score in results if score >= cutoff]
        logger.info(
            "Retrieved %d/%d chunks at or above %.3f for user '%s'",
            len(chunks), len(results), cutoff, self.user_id,
        )
        return chunks


def _tag(doc: Document, score: float, embedding_score: float, score_type: str) -> Document:
    """Fix metadata types and record the scores used to rank the chunk.

    `score` is what passages are ranked by (the reranker's score when reranking
    was used); `embedding_score` is always the original similarity score."""
    doc.metadata = _restore_types(doc.metadata)
    doc.metadata["score"] = round(float(score), 4)
    doc.metadata["embedding_score"] = round(float(embedding_score), 4)
    doc.metadata["score_type"] = score_type
    return doc


def _restore_types(metadata: dict) -> dict:
    metadata = dict(metadata)
    for field in _INT_FIELDS:
        if isinstance(metadata.get(field), float):
            metadata[field] = int(metadata[field])
    return metadata


def split_context_header(text: str) -> tuple[str, str]:
    """Split a chunk into its 'Document: ... / Section: ...' header and its body."""
    header, sep, body = text.partition("\n\n")
    if sep and header.startswith("Document: "):
        return header, body
    return "", text


def _join_with_overlap(first: str, second: str) -> str:
    """Join two texts, dropping the part at the start of `second` that repeats
    the end of `first` (chunk overlap)."""
    for size in range(min(len(first), len(second)), _MIN_OVERLAP_CHARS - 1, -1):
        if first.endswith(second[:size]):
            return first + second[size:]
    return f"{first}\n\n{second}"


def _merge_run(run: list[Document]) -> Document:
    if len(run) == 1:
        return run[0]

    body = split_context_header(run[0].page_content)[1]
    for doc in run[1:]:
        body = _join_with_overlap(body, split_context_header(doc.page_content)[1])

    first, last = run[0].metadata, run[-1].metadata
    metadata = {
        **first,
        "chunk_id": f"{first['chunk_id']}-{last['chunk_index']}",
        "chunk_index_end": last["chunk_index"],
        "score": max(d.metadata["score"] for d in run),
        "embedding_score": max(d.metadata["embedding_score"] for d in run),
        "token_count": sum(d.metadata.get("token_count", 0) for d in run),
    }
    if "page_end" in last:
        metadata["page_end"] = last["page_end"]

    # All chunks in a run share one section, so the first chunk's header fits
    header = split_context_header(run[0].page_content)[0]
    return Document(page_content=f"{header}\n\n{body}" if header else body, metadata=metadata)


def _continues(previous: Document, chunk: Document) -> bool:
    """True if `chunk` is the next piece of the same section as `previous`."""
    return (
        chunk.metadata["chunk_index"] == previous.metadata["chunk_index"] + 1
        and chunk.metadata.get("section") == previous.metadata.get("section")
    )


def merge_adjacent(chunks: list[Document]) -> list[Document]:
    """Join retrieved chunks that are consecutive pieces of the same section.

    Different sections stay separate passages so each keeps a precise citation.
    Results stay ordered by relevance (best score of each passage)."""
    by_document: dict[str, list[Document]] = defaultdict(list)
    for chunk in chunks:
        by_document[chunk.metadata["document_id"]].append(chunk)

    passages: list[Document] = []
    for doc_chunks in by_document.values():
        doc_chunks.sort(key=lambda d: d.metadata["chunk_index"])
        run = [doc_chunks[0]]
        for chunk in doc_chunks[1:]:
            if _continues(run[-1], chunk):
                run.append(chunk)
            else:
                passages.append(_merge_run(run))
                run = [chunk]
        passages.append(_merge_run(run))

    passages.sort(key=lambda d: d.metadata["score"], reverse=True)
    return passages
