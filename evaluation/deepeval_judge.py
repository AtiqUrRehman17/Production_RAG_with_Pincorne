"""AI judge, part 2: DeepEval checks that RAGAS doesn't have, each with a reason.

The same judge model as RAGAS (JUDGE_MODEL, on Groq) scores every answered
question 0-1 and writes WHY it gave that score:

  correctness           the facts the answer states agree with the expected answer
                        (meaning, not wording; missing facts are completeness)
  citation_quality      every claim has a [n] citation and source [n] supports it
  completeness          the answer covers every part of the question and every
                        key point of the expected answer
  contextual_relevancy  how much of the retrieved text is relevant to the question
                        (DeepEval's built-in metric; one judge call per passage)

The first three are G-Eval metrics: the grading rules are written below in plain
English. The steps are fixed (instead of letting the judge write them), so the
scores are steadier and each check costs one call.

A score of at least DEEPEVAL_THRESHOLD counts as a pass for that check. Like the
RAGAS scores, these don't change whether a question passed. The rules for which
questions are judged are the same as RAGAS (judge.judgeable): only answerable
questions, and a "not found" answer gets only contextual relevancy.
"""

import asyncio
import os
import threading
import warnings
from collections.abc import Callable
from statistics import mean

from evaluation.judge import MAX_JUDGE_TOKENS, JudgeInput, daily_limit_message, groq_client, judgeable
from utils.config import Settings
from utils.exceptions import JudgeError
from utils.logger import get_logger

logger = get_logger(__name__)

METRICS = (
    # name, label
    ("correctness", "Correctness"),
    ("citation_quality", "Citation quality"),
    ("completeness", "Completeness"),
    ("contextual_relevancy", "Contextual relevancy"),
)
_NEEDS_ANSWER = {"correctness", "citation_quality", "completeness"}

# G-Eval checks: what the judge sees, and the steps it follows. "Input" is the
# question, "Actual Output" the system's answer, "Expected Output" the golden
# answer, "Retrieval Context" the numbered passages the answer was written from.
_G_EVAL = {
    "correctness": {
        "params": ("INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT"),
        "criteria": "Judge whether the facts stated in the actual output are correct, "
                    "using the expected output as the answer key.",
        "steps": [
            "List the facts the actual output states in answer to the input.",
            "Compare each fact with the expected output. A fact that means the same as the expected output "
            "is correct even if it is worded differently, but numbers, names, dates and units must match.",
            "A fact that contradicts the expected output is wrong. Any wrong fact gives a low score.",
            "Do not lower the score for facts the actual output leaves out, or for extra details the "
            "expected output doesn't mention, unless they contradict it. Only judge whether what is said is right.",
            "Ignore citation markers such as [1] and the writing style.",
        ],
    },
    "citation_quality": {
        "params": ("ACTUAL_OUTPUT", "RETRIEVAL_CONTEXT"),
        "criteria": "Judge whether every claim in the actual output cites a source, "
                    "and whether the cited source supports the claim.",
        "steps": [
            "The retrieval context is a list of numbered sources. A marker such as [2] in the actual output "
            "refers to the source starting with [2].",
            "Split the actual output into its factual claims and find the citation markers of each. A marker at "
            "the end of a sentence or list item covers that sentence or item.",
            "For each claim, check that it has a citation and that the cited source actually supports it.",
            "A claim without a citation, a citation to a source that does not support the claim, or a marker "
            "with no matching source lowers the score.",
            "Sentences that state no facts (introductions, connecting sentences) need no citation. Do not judge "
            "whether the claims answer the question.",
        ],
    },
    "completeness": {
        "params": ("INPUT", "ACTUAL_OUTPUT", "EXPECTED_OUTPUT"),
        "criteria": "Judge whether the actual output covers every part of the input question "
                    "and every key point of the expected output.",
        "steps": [
            "Split the input into every part it asks about (a two-part question has two parts).",
            "List the key points of the expected output.",
            "Check whether the actual output addresses every part of the input and includes every key point, "
            "in any wording.",
            "Each missing part or key point lowers the score. An answer that covers all of them scores high.",
            "Do not judge whether the points are correct (another check covers that). Ignore citation markers "
            "such as [1] and the writing style.",
        ],
    },
}


def parse_metrics(text: str) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(n.strip() for n in text.split(",") if n.strip()))
    known = [name for name, _ in METRICS]
    unknown = [n for n in names if n not in known]
    if unknown or not names:
        raise JudgeError(f"Unknown DeepEval metric(s): {', '.join(unknown) or '(none given)'}. "
                         f"Choose from: {', '.join(known)}")
    return names


def _import_deepeval():
    """Import DeepEval with its usage statistics turned off."""
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    import deepeval  # noqa: F401
    return deepeval


class DeepEvalJudge:
    def __init__(self, settings: Settings, metrics: tuple[str, ...]):
        client, extra = groq_client(settings)
        _import_deepeval()
        from deepeval.metrics import ContextualRelevancyMetric, GEval
        from deepeval.models import DeepEvalBaseLLM
        from deepeval.test_case import SingleTurnParams

        model_name = settings.judge_model

        class GroqJudgeModel(DeepEvalBaseLLM):
            """The judge model on Groq, for DeepEval. Answers that DeepEval reads as
            JSON are requested in JSON mode."""

            def __init__(self):
                super().__init__(model_name)

            def load_model(self):
                return client

            async def a_generate(self, prompt: str, schema=None, **kwargs) -> str:
                options = {"response_format": {"type": "json_object"}} if schema else {}
                response = await client.chat.completions.create(
                    model=model_name, messages=[{"role": "user", "content": prompt}],
                    temperature=0, max_tokens=MAX_JUDGE_TOKENS, **extra, **options,
                )
                return response.choices[0].message.content or ""

            def generate(self, prompt: str, schema=None, **kwargs) -> str:
                # Every metric is run with a_measure, so only a_generate is used
                raise NotImplementedError("The Groq judge is only called asynchronously.")

            def get_model_name(self) -> str:
                return f"groq {model_name}"

        model = GroqJudgeModel()
        self.metrics = metrics
        self.model = model_name
        self.threshold = settings.deepeval_threshold
        self.stopped: str | None = None  # set when Groq's daily limit is reached
        self._scorers = {}
        for name in metrics:
            if name == "contextual_relevancy":
                self._scorers[name] = ContextualRelevancyMetric(
                    threshold=self.threshold, model=model, include_reason=True, async_mode=True)
            else:
                check = _G_EVAL[name]
                self._scorers[name] = GEval(
                    name=name, criteria=check["criteria"], evaluation_steps=check["steps"],
                    evaluation_params=[getattr(SingleTurnParams, p) for p in check["params"]],
                    model=model, threshold=self.threshold, async_mode=True,
                )
        # One event loop for every call, so the async client is never used across loops;
        # the lock keeps two threads from running it at once (a metric keeps its last result)
        self._loop = asyncio.new_event_loop()
        self._lock = threading.Lock()

    @property
    def label(self) -> str:
        return f"DeepEval, groq {self.model}"

    def _test_case(self, sample: JudgeInput):
        from deepeval.test_case import LLMTestCase

        # Numbered like the passages the answer model saw, so [n] citations can be checked
        return LLMTestCase(
            input=sample.question,
            actual_output=sample.cited_answer or "",
            expected_output=sample.reference,
            retrieval_context=[f"[{n}] {text}" for n, text in enumerate(sample.contexts, start=1)],
        )

    def score(self, sample: JudgeInput) -> tuple[dict, dict, dict]:
        """Scores for one question, the judge's reasons, and the metrics that failed."""
        scores, reasons, errors = {}, {}, {}
        test_case = self._test_case(sample)
        for name in self.metrics:
            if (name in _NEEDS_ANSWER and sample.cited_answer is None) or not sample.contexts:
                continue  # "not found" answers aren't graded; no passages: nothing to grade
            if self.stopped:
                errors[name] = self.stopped
                continue
            metric = self._scorers[name]
            try:
                with self._lock, warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    value = self._loop.run_until_complete(metric.a_measure(test_case, _show_indicator=False))
                scores[name] = round(float(value), 4)
                reasons[name] = " ".join(str(metric.reason or "").split())
            except Exception as exc:
                self.stopped = daily_limit_message(exc)
                if not self.stopped:
                    logger.warning("DeepEval could not score %s: %s", name, exc)
                errors[name] = self.stopped or " ".join(str(exc).split())[:300]
        return scores, reasons, errors


def averages(records: list[dict], threshold: float) -> dict:
    """Average and pass count of every DeepEval metric over the questions it was given for."""
    summary = {}
    for name, _ in METRICS:
        values = [r["deepeval"][name] for r in records if name in (r.get("deepeval") or {})]
        if values:
            summary[name] = {"value": mean(values), "n": len(values),
                             "passed": sum(v >= threshold for v in values)}
    return summary


def deepeval_run(run: dict, judge: DeepEvalJudge,
                 on_item: Callable[[int, int, dict], None] | None = None) -> dict:
    """Add DeepEval's scores and reasons to a run from `evaluate` (a new or a saved one)."""
    to_judge = judgeable(run, "deepeval")
    for index, (record, sample) in enumerate(to_judge, start=1):
        scores, reasons, errors = judge.score(sample)
        record["deepeval"] = scores
        record["deepeval_reasons"] = reasons
        if errors:
            record["deepeval_errors"] = errors
        if on_item:
            on_item(index, len(to_judge), record)

    run["deepeval"] = {
        "judge": judge.label,
        "metrics": list(judge.metrics),
        "threshold": judge.threshold,
        "summary": averages(run["results"], judge.threshold),
        "failed": sum(len(r.get("deepeval_errors", {})) for r in run["results"]),
        "stopped": judge.stopped,
    }
    return run
