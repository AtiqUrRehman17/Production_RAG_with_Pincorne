"""Run and read golden-dataset evaluations (admin only), like `python main.py evaluate`.

A run is a background job (it can take many minutes); follow it with
GET /api/v1/admin/jobs/{id}. Results are saved in EVAL_RESULTS_DIR, the same
files the CLI writes, so --compare works on runs started from either side.
"""

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from api.dependencies import JobQueue, get_queue, require_admin
from api.errors import APIError
from api.schemas.admin import EvaluationRequest, EvaluationSummary
from api.schemas.documents import JobOut
from evaluation.dataset import load_dataset
from evaluation.report import compare_runs, load_run
from evaluation.runner import check_documents
from utils.config import get_settings
from utils.request_context import current_request_id
from workers import jobs, queue

router = APIRouter(prefix="/admin/evaluations", tags=["admin: evaluations"], dependencies=[Depends(require_admin)])

_TAG = r"^[A-Za-z0-9_-]{1,40}$"


def _load(tag: str) -> dict:
    # Only tags, never paths: load_run would also open any file path it is given
    if not re.fullmatch(_TAG[1:-1], tag):
        raise APIError(400, "invalid_tag", "A tag may only contain letters, numbers, '-' and '_'.")
    try:
        return load_run(tag, get_settings().eval_results_dir)
    except Exception as exc:
        raise APIError(404, "evaluation_not_found", f"No saved evaluation run with tag '{tag}' was found.") from exc


def _check(body: EvaluationRequest) -> None:
    """Fail now, not minutes later in the worker."""
    from evaluation.deepeval_judge import parse_metrics as parse_deepeval
    from evaluation.judge import parse_metrics as parse_ragas

    settings = get_settings()
    if body.ragas:
        parse_ragas(",".join(body.ragas_metrics) if body.ragas_metrics else settings.judge_metrics)
    if body.deepeval:
        parse_deepeval(",".join(body.deepeval_metrics) if body.deepeval_metrics else settings.deepeval_metrics)
    if body.saved_run:
        if not (body.ragas or body.deepeval):
            raise APIError(400, "no_judge", "Grading a saved run needs ragas and/or deepeval set to true.")
        _load(body.saved_run)
        return
    dataset = load_dataset(settings.eval_dataset_path)
    check_documents(dataset, settings.eval_user_id, settings)
    if body.ids:
        unknown = sorted(set(body.ids) - {item.id for item in dataset.items})
        if unknown:
            raise APIError(400, "unknown_question", f"Unknown question id(s): {', '.join(unknown)}")


@router.post("", response_model=JobOut, status_code=202, summary="Start an evaluation run (background job)")
async def start_evaluation(body: EvaluationRequest, job_queue: JobQueue = Depends(get_queue)) -> JobOut:
    if jobs.find_active_job(type="evaluation"):
        raise APIError(409, "evaluation_running", "An evaluation is already running; wait for it to finish "
                                                  "(the free-tier limits are shared).")
    _check(body)
    settings = get_settings()
    tag = body.tag or ("retrieval" if body.retrieval_only else "full") + ("-no-rerank" if body.no_rerank else "")
    params = body.model_dump() | {"tag": body.tag if body.saved_run else tag, "user_id": settings.eval_user_id}
    for key in ("ragas_metrics", "deepeval_metrics"):
        params[key] = ",".join(params[key]) if params[key] else None
    job = jobs.create_job("evaluation", settings.eval_user_id, request_id=current_request_id(), params=params)
    try:
        await job_queue.enqueue(queue.EVALUATION, job.id, job_id=job.id)
    except APIError as exc:
        jobs.fail_job(job.id, exc.message)
        raise
    return JobOut.model_validate(job)


def _summary(path: Path) -> EvaluationSummary | None:
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
        return EvaluationSummary(
            tag=run["tag"], file=path.name, dataset=run["dataset"], mode=run["mode"],
            started_at=run["started_at"], duration_seconds=run.get("duration_seconds"),
            questions=len(run["results"]), passed=run["summary"].get("passed"),
            judges=[key for key in ("ragas", "deepeval") if run.get(key)],
        )
    except Exception:
        return None  # not a run file (or from a much older version)


@router.get("", response_model=list[EvaluationSummary], summary="Saved evaluation runs, newest first")
def list_evaluations() -> list[EvaluationSummary]:
    files = sorted(get_settings().eval_results_dir.glob("*.json"), reverse=True)
    return [summary for summary in map(_summary, files) if summary]


@router.get("/compare", summary="Compare two saved runs (what changed from A to B)")
def compare(a: str = Query(..., pattern=_TAG), b: str = Query(..., pattern=_TAG)) -> dict:
    return compare_runs(_load(a), _load(b))


@router.get("/{tag}", summary="A saved run with every question's result (the latest run with this tag)")
def get_evaluation(tag: str) -> dict:
    return _load(tag)
