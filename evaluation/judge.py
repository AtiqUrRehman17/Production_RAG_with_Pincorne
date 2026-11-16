"""AI judge: RAGAS metrics that grade answers by meaning, not by matching words.

A separate model (JUDGE_MODEL, on Groq) reads the question, the answer, the
passages the answer was written from and the expected answer, and scores 0-1:

  faithfulness       every claim in the answer is supported by the passages
                     (low = hallucinated details)
  answer_relevancy   the answer addresses the question (the judge writes the
                     questions the answer would fit; they are compared with the
                     real one using Gemini embeddings)
  context_precision  the passages useful for the expected answer are ranked on top
  context_recall     everything in the expected answer is found in the passages

Only answerable questions are judged. A "not found" answer gets only the two
context scores (was the information retrieved?). A score the judge could not
give (e.g. a rate limit) is left out, never counted as 0.

The judge's scores are shown next to the word-based scores in metrics.py; they
don't change whether a question passed.
"""

import asyncio
import os
import re
import sys
import threading
import types
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean

from llm.rag_chain import strip_citations
from utils.config import Settings
from utils.exceptions import JudgeError
from utils.logger import get_logger

logger = get_logger(__name__)

METRICS = (
    # name, label
    ("faithfulness", "Faithfulness"),
    ("answer_relevancy", "Answer relevancy"),
    ("context_precision", "Context precision"),
    ("context_recall", "Context recall"),
)
_NEEDS_ANSWER = {"faithfulness", "answer_relevancy"}
# Answers below this faithfulness are listed in the report to be read by a person
LOW_FAITHFULNESS = 0.8

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# Most the judge may write per call. Groq's free tier allows qwen 1,000 output tokens
# per minute and refuses a request asking for more; a verdict needs a few hundred.
MAX_JUDGE_TOKENS = 900
_MAX_RETRIES = 6  # rate limits (429) are retried after the wait Groq asks for
_TIMEOUT_SECONDS = 120
_RELEVANCY_QUESTIONS = 3  # questions the judge writes per answer (RAGAS default)


def parse_metrics(text: str) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(n.strip() for n in text.split(",") if n.strip()))
    known = [name for name, _ in METRICS]
    unknown = [n for n in names if n not in known]
    if unknown or not names:
        raise JudgeError(f"Unknown judge metric(s): {', '.join(unknown) or '(none given)'}. "
                         f"Choose from: {', '.join(known)}")
    return names


@dataclass(frozen=True)
class JudgeInput:
    question: str  # the question that was searched for (follow-ups: the rewritten one)
    answer: str | None  # None when the system said "not found" (or retrieval-only)
    contexts: list[str]
    reference: str  # the expected answer
    cited_answer: str | None = None  # the answer with its [n] citations (DeepEval checks them)


def judge_input(
    answerable: bool,
    question: str,
    reference: str | None,
    passages: list[dict],
    answer: str | None = None,
    found: bool = False,
) -> JudgeInput | None:
    """What the judge grades for one question, or None if it can't be judged."""
    if not answerable or not reference:
        return None  # nothing correct to compare with; the refusal check covers these
    if passages and not all(p.get("text") for p in passages):
        raise JudgeError("These results were saved without the passage text, so they can't be judged.")
    answered = found and bool(answer)
    return JudgeInput(
        question=question,
        answer=strip_citations(answer) if answered else None,
        contexts=[p["text"] for p in passages],
        reference=reference,
        cited_answer=answer if answered else None,
    )


def daily_limit_message(exc: Exception) -> str | None:
    """A message when Groq refused because the judge model's daily limit is used up."""
    text = str(exc)
    if "per day" not in text:
        return None  # per-minute limits are retried by the client
    wait = re.search(r"try again in ([0-9hms.]+)", text)
    return ("Groq's daily limit for the judge model is used up, so the remaining questions were not judged"
            + (f" (it frees up in {wait.group(1).rstrip('.')})" if wait else ""))


def groq_client(settings: Settings):
    """The async Groq client both AI judges call, and the extra request options."""
    if not settings.groq_api_key:
        raise JudgeError("The AI judge runs on Groq, so GROQ_API_KEY must be set in .env.")
    from langsmith.wrappers import wrap_openai
    from openai import AsyncOpenAI

    # wrap_openai records the judge's calls in LangSmith traces (when tracing is on)
    client = wrap_openai(AsyncOpenAI(
        base_url=_GROQ_BASE_URL, api_key=settings.groq_api_key.get_secret_value(),
        max_retries=_MAX_RETRIES, timeout=_TIMEOUT_SECONDS,
    ))
    extra = {"reasoning_effort": settings.judge_reasoning_effort} if settings.judge_reasoning_effort else {}
    return client, extra


def judgeable(run: dict, key: str) -> list[tuple[dict, JudgeInput]]:
    """The records of a run a judge can grade, with what it grades. Scores an earlier
    run of the same judge (`key`) left on the records are removed first."""
    to_judge = []
    for record in run["results"]:
        for suffix in ("", "_errors", "_reasons"):
            record.pop(key + suffix, None)
        if record.get("error") or record.get("skipped"):
            continue
        sample = judge_input(
            record["answerable"], record.get("searched_for") or record["question"],
            record.get("expected_answer"), record.get("passages", []),
            record.get("answer"), record.get("found", False),
        )
        if sample:
            to_judge.append((record, sample))
    return to_judge


def _import_ragas():
    """Import RAGAS. It still imports a Vertex AI chat class that langchain-community 0.4
    removed, only to check `isinstance`; a placeholder lets the import succeed."""
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    name = "langchain_community.chat_models.vertexai"
    if name not in sys.modules:
        try:
            __import__(name)
        except ImportError:
            placeholder = types.ModuleType(name)
            placeholder.ChatVertexAI = type("ChatVertexAI", (), {})
            sys.modules[name] = placeholder
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import ragas  # noqa: F401
    return ragas


class Judge:
    def __init__(self, settings: Settings, metrics: tuple[str, ...]):
        client, extra = groq_client(settings)
        _import_ragas()
        from ragas.embeddings.base import BaseRagasEmbedding
        from ragas.llms import llm_factory
        from ragas.metrics.collections import (
            AnswerRelevancy,
            ContextPrecisionWithReference,
            ContextRecall,
            Faithfulness,
        )

        from embeddings.gemini import get_embeddings

        class QuestionEmbeddings(BaseRagasEmbedding):
            """Our Gemini embeddings for answer relevancy. Question is compared with
            question, so both sides use the query embedding."""

            def embed_text(self, text: str, **kwargs) -> list[float]:
                return get_embeddings().embed_query(text)

            async def aembed_text(self, text: str, **kwargs) -> list[float]:
                return await asyncio.to_thread(self.embed_text, text)

        self.metrics = metrics
        self.model = settings.judge_model
        self.stopped: str | None = None  # set when Groq's daily limit is reached
        llm = llm_factory(settings.judge_model, provider="openai", client=client,
                          temperature=0, max_tokens=MAX_JUDGE_TOKENS, **extra)
        self._scorers = {
            "faithfulness": Faithfulness(llm=llm),
            "answer_relevancy": AnswerRelevancy(llm=llm, embeddings=QuestionEmbeddings(),
                                                strictness=_RELEVANCY_QUESTIONS),
            "context_precision": ContextPrecisionWithReference(llm=llm),
            "context_recall": ContextRecall(llm=llm),
        }
        # One event loop for every call, so the async client is never used across loops;
        # the lock keeps two threads from running it at once
        self._loop = asyncio.new_event_loop()
        self._lock = threading.Lock()

    @property
    def label(self) -> str:
        return f"RAGAS, groq {self.model}"

    def _arguments(self, name: str, sample: JudgeInput) -> dict | None:
        if name in _NEEDS_ANSWER:
            if sample.answer is None:
                return None
            if name == "answer_relevancy":
                return {"user_input": sample.question, "response": sample.answer}
            return {"user_input": sample.question, "response": sample.answer, "retrieved_contexts": sample.contexts}
        if not sample.contexts:
            return None
        return {"user_input": sample.question, "reference": sample.reference, "retrieved_contexts": sample.contexts}

    def score(self, sample: JudgeInput) -> tuple[dict, dict]:
        """Scores for one question, and the metrics that failed (name -> error)."""
        scores, errors = {}, {}
        for name in self.metrics:
            arguments = self._arguments(name, sample)
            if arguments is None:
                # Retrieval found nothing: none of the expected answer was retrieved
                if name == "context_recall" and not sample.contexts:
                    scores[name] = 0.0
                continue
            if self.stopped:
                errors[name] = self.stopped
                continue
            try:
                with self._lock, warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    result = self._loop.run_until_complete(self._scorers[name].ascore(**arguments))
                scores[name] = round(float(result.value), 4)
            except Exception as exc:
                self.stopped = daily_limit_message(exc)
                if not self.stopped:
                    logger.warning("Judge could not score %s: %s", name, exc)
                errors[name] = self.stopped or " ".join(str(exc).split())[:300]
        return scores, errors


def averages(records: list[dict]) -> dict:
    """Average every judge metric over the questions it was given for."""
    summary = {}
    for name, _ in METRICS:
        values = [r["ragas"][name] for r in records if name in (r.get("ragas") or {})]
        if values:
            summary[name] = {"value": mean(values), "n": len(values)}
    return summary


def judge_run(run: dict, judge: Judge, on_item: Callable[[int, int, dict], None] | None = None) -> dict:
    """Add the judge's scores to a run from `evaluate` (a new or a saved one)."""
    to_judge = judgeable(run, "ragas")
    for index, (record, sample) in enumerate(to_judge, start=1):
        scores, errors = judge.score(sample)
        record["ragas"] = scores
        if errors:
            record["ragas_errors"] = errors
        if on_item:
            on_item(index, len(to_judge), record)

    run["ragas"] = {
        "judge": judge.label,
        "metrics": list(judge.metrics),
        "summary": averages(run["results"]),
        "failed": sum(len(r.get("ragas_errors", {})) for r in run["results"]),
        "stopped": judge.stopped,
    }
    return run
