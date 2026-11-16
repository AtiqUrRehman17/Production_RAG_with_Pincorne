"""Run a golden dataset through the real system and score every question.

It uses the same retriever, reranker, prompt and LLM (LLM_PROVIDER) as `ask`
and `chat`, so the scores describe exactly what users get.

  retrieval-only: only the retriever runs (no LLM answers, cheaper)
  full:           RAGChain.ask runs (rewrite + retrieval + LLM), then both the
                  retrieved passages and the answer are scored
"""

import time
from collections.abc import Callable
from datetime import datetime, timezone

from langchain_core.documents import Document

from evaluation.dataset import QUESTION_TYPES, Dataset, DatasetError, EvalItem
from evaluation.metrics import answer_scores, is_useful, item_passed, retrieval_scores, summarize
from ingestion.registry import DocumentRegistry
from llm.rag_chain import ChatTurn, RAGChain
from retrieval.retriever import DocumentRetriever
from utils.config import Settings
from utils.exceptions import RAGError
from utils.logger import get_logger
from utils.tracing import trace_scope

logger = get_logger(__name__)

# Saved with every run, so it is always clear which configuration was measured
SETTINGS_TO_RECORD = (
    "llm_provider", "llm_model", "gemini_llm_model", "llm_thinking_level", "groq_llm_model",
    "groq_temperature", "gemini_embedding_model", "embedding_dimension",
    "chunk_size", "chunk_overlap", "min_chunk_size",
    "top_k", "min_relevance_score", "relative_score_margin",
    "reranker_enabled", "rerank_model", "retrieval_fetch_k", "rerank_top_n",
    "rerank_min_score", "rerank_min_best_score", "chat_history_turns",
)


def check_documents(dataset: Dataset, user_id: str, settings: Settings) -> None:
    """The dataset's documents must be uploaded for the evaluation user."""
    uploaded = {r.file_name for r in DocumentRegistry(settings).list_for_user(user_id)}
    missing = [d for d in dataset.documents if d not in uploaded]
    if missing:
        commands = "\n".join(f'  python main.py ingest "<path to {d}>" --user {user_id}' for d in missing)
        raise DatasetError(
            f"These dataset documents are not uploaded for user '{user_id}':\n{commands}"
        )


def _passage_record(item: EvalItem, doc: Document) -> dict:
    meta = doc.metadata
    record = {key: meta[key] for key in (
        "file_name", "section", "page_number", "page_end", "chunk_index", "chunk_index_end",
        "score", "embedding_score", "score_type",
    ) if key in meta}
    record["useful"] = is_useful(item, meta)
    record["text"] = doc.page_content  # kept for the LLM-judge step later
    return record


def _run_item(item: EvalItem, retriever: DocumentRetriever, chain: RAGChain | None) -> dict:
    record = {
        "id": item.id, "question": item.question, "type": item.type, "answerable": item.answerable,
        "expected_answer": item.expected_answer, "scores": {}, "passed": None,
    }
    retrieval_only = chain is None
    try:
        started = time.perf_counter()
        if retrieval_only:
            if item.history:
                record["skipped"] = "follow-up questions need the chat rewrite step (run the full evaluation)"
                return record
            passages = retriever.invoke(item.question)
            scores = retrieval_scores(item, [p.metadata for p in passages])
        else:
            history = [ChatTurn(turn.question, turn.answer) for turn in item.history]
            answer = chain.ask(item.question, history=history)
            passages = answer.passages
            record.update(
                searched_for=answer.standalone_question,
                answer=answer.text,
                found=answer.found,
                citations=[{"number": c.number, "label": c.label, "useful": is_useful(item, c.passage.metadata)}
                           for c in answer.citations],
                invalid_citations=answer.invalid_citation_numbers,
            )
            scores = {
                **retrieval_scores(item, [p.metadata for p in passages]),
                **answer_scores(item, answer.text, answer.found,
                                [c.passage.metadata for c in answer.citations],
                                answer.invalid_citation_numbers),
            }
        record["seconds"] = round(time.perf_counter() - started, 2)
        record["passages"] = [_passage_record(item, p) for p in passages]
        record["scores"] = scores
        record["passed"] = item_passed(item, scores, retrieval_only)
    except RAGError as exc:
        # One failing question (e.g. a rate limit) shouldn't stop the whole run.
        # An error is not a wrong answer: it is left unjudged (passed = None) and
        # counted separately, so it doesn't lower the quality scores.
        cause = exc.__cause__
        logger.warning("[%s] error: %s", item.id, cause or exc)
        record["error"] = str(exc)
        record["error_cause"] = " ".join(str(cause).split())[:300] if cause else None
        record["passed"] = None
    return record


def run_evaluation(
    dataset: Dataset,
    settings: Settings,
    user_id: str,
    retrieval_only: bool = False,
    tag: str = "run",
    on_item: Callable[[int, int, dict], None] | None = None,
) -> dict:
    check_documents(dataset, user_id, settings)

    if retrieval_only:
        chain = None
        retriever = DocumentRetriever.for_user(user_id, settings)
    else:
        chain = RAGChain(user_id, settings)
        retriever = chain.retriever

    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    results = []
    for index, item in enumerate(dataset.items, start=1):
        # Labels each question's LangSmith trace, so it can be found by its id
        with trace_scope(
            metadata={"question_id": item.id, "question_type": item.type,
                      "dataset": dataset.label, "eval_mode": "retrieval-only" if retrieval_only else "full",
                      "eval_tag": tag},
        ):
            record = _run_item(item, retriever, chain)
        results.append(record)
        if on_item:
            on_item(index, len(dataset.items), record)

    by_type = {}
    for kind in QUESTION_TYPES:
        subset = [r for r in results if r["type"] == kind]
        if subset:
            by_type[kind] = summarize(subset)

    return {
        "tag": tag,
        "dataset": dataset.label,
        "dataset_path": str(dataset.path),
        "mode": "retrieval-only" if retrieval_only else "full",
        "user_id": user_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "duration_seconds": round(time.perf_counter() - started, 1),
        "rerank_requests": retriever.reranker.requests_made if retriever.reranker else 0,
        "settings": {name: getattr(settings, name) for name in SETTINGS_TO_RECORD},
        "summary": summarize(results),
        "by_type": by_type,
        "results": results,
    }
