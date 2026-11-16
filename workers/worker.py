"""The background worker: takes jobs from the Redis queue and runs them (workers/tasks.py)."""

from arq import cron, func
from arq.worker import Worker

from database.engine import get_engine
from database.log_handler import disable_database_logging, enable_database_logging
from utils.config import get_settings
from utils.logger import get_logger
from utils.tracing import flush_traces
from workers import queue, recovery, tasks

logger = get_logger(__name__)

_MINUTE = 60


async def _startup(ctx: dict) -> None:
    enable_database_logging("worker")
    get_engine()  # create the tables now, not during the first job
    await recovery.start_heartbeat(ctx)
    logger.info("Worker started (queue '%s', up to %d jobs at a time)",
                queue.QUEUE_NAME, get_settings().worker_max_jobs)


async def _shutdown(ctx: dict) -> None:
    await recovery.stop_heartbeat(ctx)
    logger.info("Worker stopped")
    flush_traces()
    disable_database_logging()


def create_worker() -> Worker:
    settings = get_settings()
    return Worker(
        functions=[
            func(tasks.ingest_job, name=queue.INGEST, timeout=30 * _MINUTE, max_tries=tasks.INGEST_TRIES),
            func(tasks.delete_job, name=queue.DELETE, timeout=10 * _MINUTE, max_tries=tasks.DELETE_TRIES),
            func(tasks.evaluation_job, name=queue.EVALUATION, timeout=6 * 60 * _MINUTE, max_tries=1),
            func(tasks.feedback_job, name=queue.FEEDBACK, timeout=2 * _MINUTE, max_tries=tasks.FEEDBACK_TRIES),
            func(tasks.transfer_job, name=queue.TRANSFER, timeout=30 * _MINUTE, max_tries=tasks.TRANSFER_TRIES),
        ],
        cron_jobs=[
            cron(tasks.cleanup_job, hour={3}, minute={0}, run_at_startup=True),
            cron(tasks.recover_job, second={0}, run_at_startup=True, timeout=_MINUTE),  # every minute
        ],
        redis_settings=queue.redis_settings(settings),
        queue_name=queue.QUEUE_NAME,
        max_jobs=settings.worker_max_jobs,
        on_startup=_startup,
        on_shutdown=_shutdown,
        health_check_interval=30,
        keep_result=3600,
    )
