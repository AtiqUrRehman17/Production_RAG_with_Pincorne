"""The job queue in Redis, shared by the API (puts jobs in) and the worker (takes them out)."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from utils.config import Settings

QUEUE_NAME = "rag:queue"

# Job names the worker knows (see workers/worker.py)
INGEST = "ingest"
DELETE = "delete"
EVALUATION = "evaluation"
FEEDBACK = "feedback"
TRANSFER = "transfer"


def redis_settings(settings: Settings, retries: int = 5) -> RedisSettings:
    """Connection settings from REDIS_URL. `retries`: connection attempts, one second apart."""
    redis = RedisSettings.from_dsn(settings.redis_url)
    redis.conn_retries = retries
    return redis


async def connect(settings: Settings, retries: int = 5) -> ArqRedis:
    return await create_pool(redis_settings(settings, retries), default_queue_name=QUEUE_NAME)


def worker_health_key() -> str:
    """Redis key the worker refreshes while it runs (it expires when the worker stops)."""
    from arq.constants import health_check_key_suffix

    return QUEUE_NAME + health_check_key_suffix
