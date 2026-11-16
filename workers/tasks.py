"""The work the background worker does. Each job runs the same code as the CLI.

  ingest      validate -> chunk -> embed -> store (ingestion/service.py)
  delete      remove a document's vectors, file and record
  evaluation  run the golden dataset, optionally graded by the AI judges
  feedback    copy a thumbs up / down to the answer's LangSmith trace
  transfer    give the documents and chats made without accounts to the first account
  cleanup     daily: delete app logs older than LOG_RETENTION_DAYS
  recover     every minute: release jobs whose worker stopped without warning (workers/recovery.py)

The pipeline code is blocking (network calls), so it runs in a thread and the
worker stays free to start other jobs. Each job's logs and traces carry the
request ID of the API call that created it.
"""

import asyncio
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from arq import Retry

from database.log_handler import delete_old_logs
from database.models import Job
from ingestion.registry import DocumentRegistry
from ingestion.service import delete_document, ingest_document
from utils.config import get_settings
from utils.exceptions import (
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmbeddingError,
    RAGError,
    VectorStoreError,
)
from utils.logger import get_logger
from utils.request_context import request_id_var
from utils.tracing import model_labels, trace_scope
from workers import jobs, recovery

logger = get_logger(__name__)

INGEST_TRIES = 3
DELETE_TRIES = 3
TRANSFER_TRIES = 3
FEEDBACK_TRIES = 3
# Errors that may pass if the job is tried again a little later
_PASSING_ERRORS = (EmbeddingError, VectorStoreError, ConnectionError, TimeoutError)
_RETRY_DELAY_SECONDS = 30  # x the attempt number: 30 s, then 60 s


@contextmanager
def _job_scope(job: Job) -> Iterator[None]:
    """Logs and traces of the job carry its request ID (that of the API call that created it)."""
    token = request_id_var.set(job.request_id or job.id)
    try:
        metadata = {"job_id": job.id, "job_type": job.type, "user_id": job.user_id,
                    "request_id": job.request_id, **model_labels(get_settings())}
        with trace_scope(tags=["worker", job.type], metadata=metadata):
            yield
    finally:
        request_id_var.reset(token)


async def _run(ctx: dict, job_id: str, work: Callable[[Job], dict], max_tries: int,
               on_end: Callable[[Job], None] | None = None) -> None:
    """Run `work` for a job and record the outcome. `on_end` runs once the job is done
    or has finally failed (not when it will be tried again)."""
    attempt = ctx["job_try"]
    job = jobs.start_job(job_id, attempt)
    if job is None:
        return  # deleted, or already done by an earlier attempt
    await recovery.claim(ctx, job.id)  # so the job can be released if this worker stops without warning
    try:
        await _run_claimed(job, job_id, work, attempt, max_tries, on_end)
    finally:
        await recovery.unclaim(ctx, job.id)


async def _run_claimed(job: Job, job_id: str, work: Callable[[Job], dict], attempt: int, max_tries: int,
                       on_end: Callable[[Job], None] | None) -> None:
    with _job_scope(job):
        logger.info("Job %s (%s) started, attempt %d", job.id, job.type, attempt)
        try:
            result = await asyncio.to_thread(work, job)
        except asyncio.CancelledError:
            # The worker is stopping, or the job ran past its time limit
            jobs.fail_job(job_id, "The job was interrupted (the worker stopped or the time limit was "
                                  "reached). If the worker was restarted, it is tried again.")
            raise
        except Exception as exc:
            if isinstance(exc, _PASSING_ERRORS) and attempt < max_tries:
                delay = _RETRY_DELAY_SECONDS * attempt
                logger.warning("Job %s attempt %d failed (%s); trying again in %d s", job.id, attempt, exc, delay)
                jobs.update_job(job_id, status="queued",
                                error=f"Attempt {attempt} failed: {exc} Trying again in {delay} seconds.")
                raise Retry(defer=delay) from exc
            if isinstance(exc, RAGError):
                logger.warning("Job %s failed: %s", job.id, exc)
                message = str(exc)
            else:
                logger.exception("Job %s crashed", job.id)
                message = f"Unexpected error (reference {job.request_id or job.id}). See the admin logs."
            jobs.fail_job(job_id, message)
        else:
            jobs.finish_job(job_id, result)
            logger.info("Job %s (%s) done", job.id, job.type)
        if on_end:
            on_end(job)


# ---------------------------------------------------------------- ingest
def _ingest(job: Job) -> dict:
    settings = get_settings()
    already_uploaded = False
    try:
        record = ingest_document(Path(job.params["path"]), job.user_id, settings)
    except DuplicateDocumentError as exc:
        # Uploaded meanwhile (or by an earlier attempt of this job): the document is there
        record = DocumentRegistry(settings).get(exc.existing_document_id)
        already_uploaded = True
    return {"document_id": record.document_id, "file_name": record.file_name,
            "chunks": record.chunk_count, "pages": record.page_count, "already_uploaded": already_uploaded}


def _remove_upload(job: Job) -> None:
    # The file waited in INCOMING_DIR/<job id>/; ingest keeps its own copy in UPLOAD_DIR
    shutil.rmtree(Path(job.params["path"]).parent, ignore_errors=True)


async def ingest_job(ctx: dict, job_id: str) -> None:
    await _run(ctx, job_id, _ingest, INGEST_TRIES, on_end=_remove_upload)


# ---------------------------------------------------------------- delete
def _delete(job: Job) -> dict:
    try:
        record = delete_document(job.document_id, job.user_id, get_settings())
    except DocumentNotFoundError:
        return {"document_id": job.document_id, "already_deleted": True}
    return {"document_id": record.document_id, "file_name": record.file_name, "chunks": record.chunk_count}


async def delete_job(ctx: dict, job_id: str) -> None:
    await _run(ctx, job_id, _delete, DELETE_TRIES)


# ---------------------------------------------------------------- transfer
def _transfer(job: Job) -> dict:
    from accounts.service import transfer_user_data

    # Safe to repeat: documents already moved are no longer under the old user
    return transfer_user_data(job.params["from_user"], job.user_id, get_settings())


async def transfer_job(ctx: dict, job_id: str) -> None:
    await _run(ctx, job_id, _transfer, TRANSFER_TRIES)


# ---------------------------------------------------------------- evaluation
def _evaluate(job: Job) -> dict:
    from evaluation.dataset import load_dataset
    from evaluation.deepeval_judge import DeepEvalJudge, deepeval_run
    from evaluation.deepeval_judge import parse_metrics as parse_deepeval
    from evaluation.judge import Judge, judge_run
    from evaluation.judge import parse_metrics as parse_ragas
    from evaluation.report import load_run, save_run
    from evaluation.runner import run_evaluation
    from retrieval.retriever import with_overrides

    options = job.params
    settings = with_overrides(get_settings(), no_rerank=options.get("no_rerank", False))

    def progress(step: str) -> Callable[[int, int, dict], None]:
        def report(index: int, total: int, record: dict) -> None:
            jobs.update_job(job.id, progress={"step": step, "done": index, "total": total})
        return report

    # Judges are created first, so a bad setting fails before any question is asked
    judge = Judge(settings, parse_ragas(options.get("ragas_metrics") or settings.judge_metrics)) \
        if options.get("ragas") else None
    deepeval = DeepEvalJudge(settings, parse_deepeval(options.get("deepeval_metrics") or settings.deepeval_metrics)) \
        if options.get("deepeval") else None

    if options.get("saved_run"):
        run = load_run(options["saved_run"], settings.eval_results_dir)
        run["tag"] = options.get("tag") or f"{run['tag']}-judged"[:40]
    else:
        dataset = load_dataset(settings.eval_dataset_path)
        if options.get("ids"):
            wanted = set(options["ids"])
            dataset.items = [item for item in dataset.items if item.id in wanted]
        if options.get("limit"):
            dataset.items = dataset.items[: options["limit"]]
        run = run_evaluation(dataset, settings, options.get("user_id") or settings.eval_user_id,
                             retrieval_only=options.get("retrieval_only", False), tag=options["tag"],
                             on_item=progress("questions"))
    if judge:
        judge_run(run, judge, on_item=progress("ragas"))
    if deepeval:
        deepeval_run(run, deepeval, on_item=progress("deepeval"))

    path = save_run(run, settings.eval_results_dir)
    return {
        "tag": run["tag"], "file": path.name, "mode": run["mode"], "questions": len(run["results"]),
        "passed": run["summary"].get("passed"),
        "errors": sum(1 for r in run["results"] if r.get("error")),
        "ragas": (run.get("ragas") or {}).get("summary"),
        "deepeval": (run.get("deepeval") or {}).get("summary"),
        "judge_stopped": next((j["stopped"] for j in (run.get("ragas"), run.get("deepeval")) if j and j.get("stopped")), None),
    }


async def evaluation_job(ctx: dict, job_id: str) -> None:
    await _run(ctx, job_id, _evaluate, max_tries=1)  # long and costly: never repeated automatically


# ---------------------------------------------------------------- feedback
def _send_feedback(feedback_id: str, delete: bool) -> None:
    from database.engine import session
    from database.models import Feedback
    from evaluation.langsmith_dataset import langsmith_client

    client = langsmith_client()
    if delete:
        client.delete_feedback(feedback_id)
        return
    with session() as db:
        feedback = db.get(Feedback, feedback_id)
        if feedback is None:
            return  # removed meanwhile
        trace_id, rating, comment, sent = (feedback.message.trace_id, feedback.rating,
                                           feedback.comment, feedback.sent_to_langsmith)
    score = 1 if rating > 0 else 0
    if sent:
        client.update_feedback(feedback_id, score=score, comment=comment)
    else:
        # The feedback keeps our ID in LangSmith, so later changes update the same entry
        client.create_feedback(trace_id, key="user_feedback", score=score, comment=comment,
                               feedback_id=feedback_id)
        with session() as db:
            feedback = db.get(Feedback, feedback_id)
            if feedback is not None:
                feedback.sent_to_langsmith = True
                db.commit()


async def feedback_job(ctx: dict, feedback_id: str, delete: bool = False) -> None:
    try:
        await asyncio.to_thread(_send_feedback, feedback_id, delete)
    except Exception as exc:
        if ctx["job_try"] < FEEDBACK_TRIES:
            raise Retry(defer=_RETRY_DELAY_SECONDS * ctx["job_try"]) from exc
        logger.warning("Could not send feedback %s to LangSmith: %s", feedback_id, exc)


# ---------------------------------------------------------------- cleanup
_MAX_TRIES = {"ingest": INGEST_TRIES, "delete": DELETE_TRIES, "transfer": TRANSFER_TRIES, "evaluation": 1}


async def recover_job(ctx: dict) -> None:
    """Every minute: run again (or fail) jobs whose worker stopped without warning."""
    await recovery.release_orphaned_jobs(ctx["redis"], _MAX_TRIES)


async def cleanup_job(ctx: dict) -> None:
    days = get_settings().log_retention_days
    deleted = await asyncio.to_thread(delete_old_logs, days)
    if deleted:
        logger.info("Deleted %d log line(s) older than %d days", deleted, days)
