"""Jobs left behind by a worker that stopped without warning (terminal window closed, process
killed, computer restarted).

While a worker runs a job, arq locks it (arq:in-progress:<job id>) for the longest job time limit
of the worker, 6 hours because of evaluations, so a job whose worker vanished would sit there that
long. To notice sooner, every worker keeps a short-lived "alive" key and notes which job it took.
A locked job whose worker is no longer alive is released: arq runs it again (it is still in the
queue), or, when it has used all its tries, it is marked failed.
"""

import asyncio
import uuid
from datetime import timedelta

from arq.connections import ArqRedis
from arq.constants import in_progress_key_prefix, job_key_prefix, retry_key_prefix

from database.models import utc_now
from utils.logger import get_logger
from workers import jobs, queue

logger = get_logger(__name__)

ALIVE_SECONDS = 60  # a worker that hasn't refreshed its key for this long is gone
_REFRESH_SECONDS = 20
_OWNER_SECONDS = 7 * 3600  # longer than any lock
_GRACE = timedelta(seconds=ALIVE_SECONDS)  # a job taken this recently may not be noted yet


def _alive_key(worker_id: str) -> str:
    return f"rag:worker:{worker_id}"


def _owner_key(job_id: str) -> str:
    return f"rag:job-owner:{job_id}"


async def start_heartbeat(ctx: dict) -> None:
    """Worker start: a unique ID, and a key that stays alive as long as the worker does."""
    worker_id = uuid.uuid4().hex
    redis: ArqRedis = ctx["redis"]
    await redis.set(_alive_key(worker_id), "1", ex=ALIVE_SECONDS)

    async def beat() -> None:
        while True:
            await asyncio.sleep(_REFRESH_SECONDS)
            try:
                await redis.set(_alive_key(worker_id), "1", ex=ALIVE_SECONDS)
            except Exception:
                logger.warning("Could not refresh the worker's alive key in Redis", exc_info=True)

    ctx["worker_id"] = worker_id
    ctx["heartbeat"] = asyncio.create_task(beat())


async def stop_heartbeat(ctx: dict) -> None:
    task = ctx.pop("heartbeat", None)
    if task:
        task.cancel()
    if "worker_id" in ctx:
        await ctx["redis"].delete(_alive_key(ctx["worker_id"]))


async def claim(ctx: dict, job_id: str) -> None:
    """Note that this worker is running the job."""
    if "worker_id" in ctx:
        await ctx["redis"].set(_owner_key(job_id), ctx["worker_id"], ex=_OWNER_SECONDS)


async def unclaim(ctx: dict, job_id: str) -> None:
    await ctx["redis"].delete(_owner_key(job_id))


async def release_orphaned_jobs(redis: ArqRedis, max_tries: dict[str, int]) -> int:
    """Release the locks of jobs whose worker is gone. `max_tries`: per job type.
    Returns how many jobs were released."""
    released = 0
    async for key in redis.scan_iter(match=f"{in_progress_key_prefix}*"):
        job_id = (key.decode() if isinstance(key, bytes) else key).removeprefix(in_progress_key_prefix)
        job = await asyncio.to_thread(jobs.get_job, job_id)
        if job is None or job.status == "done" or await redis.zscore(queue.QUEUE_NAME, job_id) is None:
            continue  # not one of ours (feedback and cron jobs have no record), or nothing left to run
        # ("failed" can still be in the queue: a worker stopped with Ctrl+C marks its job failed, "tried again")
        if (job.started_at or job.created_at) > utc_now() - _GRACE:
            continue
        owner = await redis.get(_owner_key(job_id))
        if owner and await redis.exists(_alive_key(owner.decode() if isinstance(owner, bytes) else owner)):
            continue  # its worker is still running it

        tries = int(await redis.get(retry_key_prefix + job_id) or 0)
        await redis.delete(key, _owner_key(job_id))
        if tries >= max_tries.get(job.type, 1):
            # arq would drop it without running our code, leaving the record "processing" forever
            await redis.zrem(queue.QUEUE_NAME, job_id)
            await redis.delete(job_key_prefix + job_id, retry_key_prefix + job_id)
            await asyncio.to_thread(jobs.fail_job, job_id, "The worker stopped while working on this job, "
                                                           "and it has no tries left. Please start it again.")
            logger.warning("Job %s (%s) failed: its worker stopped and no tries are left", job_id, job.type)
        else:
            await asyncio.to_thread(jobs.update_job, job_id, status="queued",
                                    error="The worker stopped while working on this job; it is tried again.")
            logger.warning("Job %s (%s) released: its worker stopped; it runs again", job_id, job.type)
        released += 1
    return released
