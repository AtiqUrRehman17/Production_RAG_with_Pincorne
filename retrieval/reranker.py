"""Second-stage reranking with a Pinecone-hosted model, through LangChain's PineconeRerank.

Embeddings turn the question and each chunk into numbers separately, so their
scores are bunched together (relevant ~0.62-0.80, unrelated ~0.55-0.72). A
reranker reads the question and each chunk together and scores how well the
chunk answers it (0-1), which separates right from wrong chunks far more clearly.

PineconeRerank logs errors and returns an empty list instead of raising. Here an
empty result for a non-empty input is treated as a failure (None), so the
retriever can fall back to embedding scores instead of wrongly answering
"not found".
"""

from langchain_core.documents import Document
from langchain_pinecone import PineconeRerank

from utils.config import Settings
from utils.exceptions import ConfigurationError
from utils.logger import get_logger
from utils.tracing import text_preview, traced

logger = get_logger(__name__)


def _where(doc: Document) -> str:
    meta = doc.metadata
    page = f", page {int(meta['page_number'])}" if meta.get("page_number") is not None else ""
    return f"{meta.get('file_name', '?')}{page} ({meta.get('section') or 'no section'})"


def _trace_inputs(inputs: dict) -> dict:
    """The trace shows each candidate's location and the start of its text."""
    return {
        "query": inputs.get("query"),
        "candidates": [
            {"where": _where(doc), "text": text_preview(doc.page_content, 200)}
            for doc in inputs.get("documents") or []
        ],
    }


def _trace_outputs(ranked: list[tuple[Document, float]] | None) -> dict:
    if ranked is None:
        return {"failed": True, "note": "reranking failed; the retriever falls back to embedding scores"}
    return {"ranked": [{"score": round(score, 4), "where": _where(doc)} for doc, score in ranked]}


class Reranker:
    def __init__(self, settings: Settings):
        self.model = settings.rerank_model
        self.top_n = settings.rerank_top_n
        self.requests_made = 0  # each one counts toward the monthly rerank quota
        try:
            self._client = PineconeRerank(
                model=settings.rerank_model,
                top_n=settings.rerank_top_n,
                pinecone_api_key=settings.pinecone_api_key.get_secret_value(),
            )
        except ValueError as exc:
            # A wrong setting is permanent, so fail clearly instead of silently falling back
            raise ConfigurationError(
                f"RERANK_MODEL '{settings.rerank_model}' is not a supported Pinecone reranker. "
                "Use bge-reranker-v2-m3, or set RERANKER_ENABLED=false."
            ) from exc

    @traced(name="rerank", run_type="chain", process_inputs=_trace_inputs, process_outputs=_trace_outputs)
    def rerank(self, query: str, documents: list[Document]) -> list[tuple[Document, float]] | None:
        """Return (document, score) pairs, best first, for the top `top_n` documents.

        Returns None if reranking failed, so the caller can fall back.
        """
        if not documents:
            return []
        self.requests_made += 1
        try:
            # Long chunks are cut at the model's token limit rather than rejected
            results = self._client.rerank(
                documents, query, top_n=min(self.top_n, len(documents)), truncate="END"
            )
        except Exception as exc:
            logger.warning("Reranker '%s' failed: %s", self.model, exc)
            logger.debug("Reranker failure details", exc_info=True)
            return None
        if not results:
            logger.warning("Reranker '%s' returned no results", self.model)
            return None

        ranked = [
            (documents[r["index"]], float(r["score"]))
            for r in results
            if r.get("index") is not None and 0 <= r["index"] < len(documents)
        ]
        return sorted(ranked, key=lambda pair: pair[1], reverse=True)
