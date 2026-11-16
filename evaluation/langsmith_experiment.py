"""Run the golden dataset as a LangSmith experiment.

`python main.py evaluate` scores the system locally and saves a JSON file. An
experiment runs the questions of the LangSmith dataset (uploaded with
`python main.py dataset push`) and stores every answer, trace and score in
LangSmith, where experiments can be opened, filtered and compared side by side.

The scoring is the same as `evaluate`: the evaluator rebuilds each question's
answer key from the example and calls the functions in metrics.py. No AI judge
is used yet.

  target     runs one question through the real system (retriever, or RAGChain.ask)
  evaluator  scores one question: one feedback key per metric, plus `passed`
  judge      (--judge) the AI judge's RAGAS scores, as ragas_* feedback keys
  deepeval   (--deepeval) DeepEval's scores as deepeval_* keys, with the reason as comment
  summary    totals over the experiment: pass rate, false refusals, hallucinations
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from statistics import mean

from langchain_core.documents import Document

from evaluation.dataset import Dataset
from evaluation.deepeval_judge import DeepEvalJudge
from evaluation.judge import Judge, JudgeInput, judge_input
from evaluation.langsmith_dataset import from_example, langsmith_client
from evaluation.metrics import METRICS, answer_scores, item_passed, retrieval_scores
from evaluation.report import failure_reasons
from evaluation.runner import SETTINGS_TO_RECORD, check_documents
from llm.rag_chain import ChatTurn, RAGChain
from retrieval.retriever import DocumentRetriever
from utils.config import Settings
from utils.exceptions import LangSmithError
from utils.logger import get_logger

logger = get_logger(__name__)

# Passage metadata kept in the experiment (the text is kept for the AI judges later)
_PASSAGE_KEYS = (
    "file_name", "section", "page_number", "page_end", "chunk_index", "chunk_index_end",
    "score", "embedding_score", "score_type",
)


def _passage(doc: Document) -> dict:
    record = {key: doc.metadata[key] for key in _PASSAGE_KEYS if key in doc.metadata}
    record["text"] = doc.page_content
    return record


# ---------------------------------------------------------------- target
def make_target(user_id: str, settings: Settings, retrieval_only: bool) -> Callable[[dict], dict]:
    """The function LangSmith calls once per example, with the example's inputs."""
    if retrieval_only:
        retriever = DocumentRetriever.for_user(user_id, settings)

        def rag_retrieval(inputs: dict) -> dict:
            passages = retriever.invoke(inputs["question"])
            return {"searched_for": inputs["question"], "passages": [_passage(p) for p in passages]}

        return rag_retrieval

    chain = RAGChain(user_id, settings)

    def rag_answer(inputs: dict) -> dict:
        history = [ChatTurn(t["question"], t["answer"]) for t in inputs.get("history") or ()]
        answer = chain.ask(inputs["question"], history=history)
        return {
            "answer": answer.text,
            "found": answer.found,
            "searched_for": answer.standalone_question,
            "citations": [{"number": c.number, "label": c.label} for c in answer.citations],
            "invalid_citations": answer.invalid_citation_numbers,
            "passages": [_passage(p) for p in answer.passages],
        }

    return rag_answer


# ---------------------------------------------------------------- scoring
def score_outputs(outputs: dict, example, retrieval_only: bool) -> tuple[dict, bool | None]:
    """The same scores `evaluate` gives, from a target's outputs and the answer key."""
    item = from_example(example)
    passages = outputs.get("passages") or []
    scores = retrieval_scores(item, passages)
    if not retrieval_only:
        cited = [passages[c["number"] - 1] for c in outputs.get("citations") or []
                 if 1 <= c["number"] <= len(passages)]
        scores.update(answer_scores(item, outputs.get("answer") or "", bool(outputs.get("found")),
                                    cited, outputs.get("invalid_citations") or []))
    return scores, item_passed(item, scores, retrieval_only)


def _crashed(run) -> bool:
    return bool(run.error) or not run.outputs


def make_evaluator(retrieval_only: bool):
    def rag_metrics(run, example) -> list[dict]:
        if _crashed(run):
            # A crash (e.g. a rate limit) is not a wrong answer, so it isn't scored
            return [{"key": "error", "score": 1, "comment": (run.error or "no output")[:300]}]
        scores, passed = score_outputs(run.outputs, example, retrieval_only)
        results = [{"key": name, "score": scores[name]} for name, _, _ in METRICS if name in scores]
        if passed is not None:
            comment = None if passed else "; ".join(failure_reasons({"scores": scores}))
            results.append({"key": "passed", "score": float(passed), "comment": comment})
        return results or [{"key": "passed", "score": None, "comment": "not judged in this mode"}]

    return rag_metrics


def _judge_sample(run, example) -> JudgeInput | None:
    """What the AI judges grade for one run (None: crashed, or nothing correct to compare with)."""
    if _crashed(run):
        return None
    item = from_example(example)
    outputs = run.outputs
    return judge_input(
        item.answerable, outputs.get("searched_for") or item.question, item.expected_answer,
        outputs.get("passages") or [], outputs.get("answer"), bool(outputs.get("found")),
    )


def make_judge_evaluator(judge: Judge):
    def ragas_judge(run, example) -> dict:
        sample = _judge_sample(run, example)
        if sample is None:
            return {"results": []}
        scores, errors = judge.score(sample)
        results = [{"key": f"ragas_{name}", "score": value} for name, value in scores.items()]
        results += [{"key": f"ragas_{name}", "score": None, "comment": f"the judge could not score this: {error}"}
                    for name, error in errors.items()]
        return {"results": results}

    return ragas_judge


def make_deepeval_evaluator(judge: DeepEvalJudge):
    def deepeval_judge(run, example) -> dict:
        sample = _judge_sample(run, example)
        if sample is None:
            return {"results": []}
        scores, reasons, errors = judge.score(sample)
        results = [{"key": f"deepeval_{name}", "score": value, "comment": reasons.get(name)}
                   for name, value in scores.items()]
        results += [{"key": f"deepeval_{name}", "score": None, "comment": f"the judge could not score this: {error}"}
                    for name, error in errors.items()]
        return {"results": results}

    return deepeval_judge


def make_summary_evaluator(retrieval_only: bool):
    def rag_summary(runs, examples) -> dict:
        judged = passed = errors = false_refusals = hallucinations = 0
        for run, example in zip(runs, examples):
            if _crashed(run):
                errors += 1
                continue
            scores, ok = score_outputs(run.outputs, example, retrieval_only)
            false_refusals += int(scores.get("false_refusal", 0))
            hallucinations += int(scores.get("hallucination", 0))
            if ok is not None:
                judged += 1
                passed += ok
        results = [
            {"key": "pass_rate", "score": passed / judged if judged else 0.0},
            {"key": "errors", "score": errors},
        ]
        if not retrieval_only:
            results += [{"key": "false_refusals", "score": false_refusals},
                        {"key": "hallucinations", "score": hallucinations}]
        return {"results": results}

    return rag_summary


# ---------------------------------------------------------------- experiment
def _runs_in_mode(example, retrieval_only: bool) -> bool:
    """Retrieval-only skips what only the full system can judge (as `evaluate` does)."""
    if not retrieval_only:
        return True
    item = from_example(example)
    if item.history:
        return False  # follow-ups need the chat rewrite step
    return item.answerable or item.type == "off-topic"  # unanswerable: judged on the answer


@dataclass
class ExperimentResult:
    name: str
    url: str | None
    questions: int
    skipped: int
    scores: dict[str, list[float]] = field(default_factory=dict)  # feedback key -> one score per run
    errors: int = 0

    def average(self, key: str) -> float | None:
        values = self.scores.get(key)
        return mean(values) if values else None


def run_experiment(
    dataset: Dataset,
    dataset_name: str,
    settings: Settings,
    user_id: str,
    retrieval_only: bool = False,
    splits: list[str] | None = None,
    version: str | None = None,
    repetitions: int = 1,
    prefix: str | None = None,
    judge: Judge | None = None,
    deepeval: DeepEvalJudge | None = None,
    on_result: Callable[[int, int, object, dict], None] | None = None,
) -> ExperimentResult:
    """Run the LangSmith dataset `dataset_name` through the system as an experiment.

    `dataset` is the local file the LangSmith dataset was pushed from; it says
    which documents must be uploaded for `user_id`."""
    check_documents(dataset, user_id, settings)
    client = langsmith_client()
    try:
        if not client.has_dataset(dataset_name=dataset_name):
            raise LangSmithError(f"LangSmith has no dataset '{dataset_name}'. Upload it first: "
                                 "python main.py dataset push")
        examples = list(client.list_examples(dataset_name=dataset_name, splits=splits or None, as_of=version))
    except LangSmithError:
        raise
    except Exception as exc:
        raise LangSmithError(f"Could not read dataset '{dataset_name}' from LangSmith: {exc}") from exc

    selected = [e for e in examples if _runs_in_mode(e, retrieval_only)]
    if not selected:
        raise LangSmithError(f"No questions to run in '{dataset_name}'"
                             f"{' for split(s) ' + ', '.join(splits) if splits else ''}"
                             f"{' at version ' + version if version else ''}.")

    mode = "retrieval-only" if retrieval_only else "full"
    metadata = {
        "mode": mode,
        "dataset_file": dataset.label,
        "dataset_version": version or "latest",
        "splits": ", ".join(splits) if splits else "all",
        "user_id": user_id,
        "judge": f"{judge.label}: {', '.join(judge.metrics)}" if judge else "none",
        "deepeval": (f"{deepeval.label}: {', '.join(deepeval.metrics)} (pass mark {deepeval.threshold})"
                     if deepeval else "none"),
        **{name: getattr(settings, name) for name in SETTINGS_TO_RECORD},
    }
    evaluators = [make_evaluator(retrieval_only)]
    if judge:
        evaluators.append(make_judge_evaluator(judge))
    if deepeval:
        evaluators.append(make_deepeval_evaluator(deepeval))
    try:
        results = client.evaluate(
            make_target(user_id, settings, retrieval_only),
            data=selected,
            evaluators=evaluators,
            summary_evaluators=[make_summary_evaluator(retrieval_only)],
            experiment_prefix=prefix or (mode if retrieval_only else f"{mode}-{settings.llm_provider}"),
            description=f"{dataset.label} ({mode}), answers by {settings.llm_provider} {settings.llm_model}",
            metadata=metadata,
            max_concurrency=0,  # one question at a time: stays within the free-tier rate limits
            num_repetitions=repetitions,
            blocking=False,  # results arrive one by one, so progress can be shown
        )
        summary = ExperimentResult(name=results.experiment_name, url=None,
                                   questions=len(selected) * repetitions,
                                   skipped=len(examples) - len(selected))
        for index, row in enumerate(results, start=1):
            feedback = {r.key: r for r in row["evaluation_results"]["results"]}
            for key, result in feedback.items():
                if result.score is not None:
                    summary.scores.setdefault(key, []).append(float(result.score))
            summary.errors += "error" in feedback
            if on_result:
                on_result(index, summary.questions, row["example"], feedback)
        results.wait()
        summary.url = results.url
    except LangSmithError:
        raise
    except Exception as exc:
        raise LangSmithError(f"The LangSmith experiment failed: {exc}") from exc
    logger.info("Experiment '%s' finished: %d runs", summary.name, summary.questions)
    return summary
