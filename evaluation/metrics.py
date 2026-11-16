"""Scores for one evaluated question, and totals over a whole run. No AI is used here.

Retrieval (did the right chunks reach the LLM?):
  hit             an expected source is among the passages
  reciprocal_rank 1 / position of the first useful passage (0 if none)
  precision       share of passages that are useful (expected or acceptable sources)
  context_recall  share of the expected sources that were found (two-part questions)
  correct_empty   off-topic questions: retrieval returned nothing

Answers (did the LLM answer correctly and honestly?):
  refusal_correct  answered when it should, said "not found" when it should
  key_facts        share of must-have facts present in the answer
  citations_valid  no citation points to a source that doesn't exist
  cites_expected   at least one cited source is a useful source
"""

import re
from statistics import mean

from evaluation.dataset import EvalItem, ExpectedSource

_NOISE = re.compile(r"[*`]")  # Markdown bold/code marks that LLMs add around facts
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _SPACES.sub(" ", _NOISE.sub("", text)).strip().lower()


def source_matches(source: ExpectedSource, metadata: dict) -> bool:
    if metadata.get("file_name", "").lower() != source.file.lower():
        return False
    if source.section and source.section.lower() in metadata.get("section", "").lower():
        return True
    if source.page is not None and metadata.get("page_number") is not None:
        first = metadata["page_number"]
        last = metadata.get("page_end") or first
        return first <= source.page <= last
    return False


def is_useful(item: EvalItem, metadata: dict) -> bool:
    return any(source_matches(s, metadata) for s in item.useful_sources)


def retrieval_scores(item: EvalItem, passages: list[dict]) -> dict:
    """`passages` are the metadata dicts of the retrieved passages, best first."""
    if item.type == "off-topic":
        return {"correct_empty": float(not passages)}
    if not item.answerable:
        return {}  # judged on the answer: it must say "not found"

    useful = [is_useful(item, p) for p in passages]
    first = next((i for i, u in enumerate(useful) if u), None)
    found = [any(source_matches(s, p) for p in passages) for s in item.expected_sources]
    scores = {
        "hit": float(first is not None),
        "reciprocal_rank": 1 / (first + 1) if first is not None else 0.0,
        "context_recall": sum(found) / len(found),
        "missing_sources": [s.describe() for s, ok in zip(item.expected_sources, found) if not ok],
    }
    if passages:
        scores["precision"] = sum(useful) / len(useful)
    return scores


def answer_scores(item: EvalItem, text: str, found: bool, cited: list[dict], invalid_citations: list[int]) -> dict:
    """`cited` are the metadata dicts of the passages the answer cited."""
    scores = {"refusal_correct": float(found == item.answerable)}
    if item.answerable and not found:
        scores["false_refusal"] = 1.0
    if not item.answerable and found:
        scores["hallucination"] = 1.0
    if not (item.answerable and found):
        return scores

    answer = normalize(text)
    present = [any(normalize(option) in answer for option in fact) for fact in item.key_facts]
    scores.update(
        key_facts=sum(present) / len(present),
        all_key_facts=float(all(present)),
        missing_facts=[" / ".join(fact) for fact, ok in zip(item.key_facts, present) if not ok],
        citations_valid=float(bool(cited) and not invalid_citations),
        cites_expected=float(any(is_useful(item, c) for c in cited)),
    )
    return scores


def item_passed(item: EvalItem, scores: dict, retrieval_only: bool) -> bool | None:
    """One overall pass/fail per question (None = not applicable in this mode)."""
    if retrieval_only:
        if item.type == "off-topic":
            return scores.get("correct_empty") == 1.0
        if not item.answerable:
            return None
        return scores.get("hit") == 1.0
    if not item.answerable:
        return scores.get("refusal_correct") == 1.0
    return (
        scores.get("refusal_correct") == 1.0
        and scores.get("all_key_facts") == 1.0
        and scores.get("cites_expected") == 1.0
    )


METRICS = (
    # name, label, kind ("rate" shows as %, "score" as 0-1, "count" as a number)
    ("hit", "Hit rate", "rate"),
    ("reciprocal_rank", "MRR", "score"),
    ("precision", "Precision", "rate"),
    ("context_recall", "Context recall", "rate"),
    ("correct_empty", "Correct empty (off-topic)", "rate"),
    ("refusal_correct", "Refusal correct", "rate"),
    ("key_facts", "Key facts found", "rate"),
    ("all_key_facts", "All key facts found", "rate"),
    ("citations_valid", "Citations valid", "rate"),
    ("cites_expected", "Cites the right source", "rate"),
)
COUNTS = (("false_refusal", "False refusals"), ("hallucination", "Hallucinations"))


def summarize(results: list[dict]) -> dict:
    """Average every metric over the questions it applies to."""
    summary: dict = {}
    for name, _, _ in METRICS:
        values = [r["scores"][name] for r in results if name in r["scores"]]
        if values:
            summary[name] = {"value": mean(values), "n": len(values)}
    answered = [r for r in results if "refusal_correct" in r["scores"]]  # empty in retrieval-only runs
    if answered:
        answerable = sum(1 for r in answered if r["answerable"])
        for name, _ in COUNTS:
            total = answerable if name == "false_refusal" else len(answered) - answerable
            summary[name] = {"value": sum(r["scores"].get(name, 0) for r in answered), "n": total}

    judged = [r for r in results if r["passed"] is not None]
    summary["passed"] = {"value": sum(r["passed"] for r in judged), "n": len(judged)}
    # Questions that crashed (e.g. API quota) are not judged at all
    summary["errors"] = {"value": sum(1 for r in results if r.get("error")), "n": len(results)}
    return summary
