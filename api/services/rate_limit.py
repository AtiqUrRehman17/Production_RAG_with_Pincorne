"""Limits on login and registration attempts, counted in Redis (shared by all API processes).

If Redis is down, attempts are allowed (and a warning is logged): the passwords
are still checked, only the limit is skipped.
"""

from api.dependencies import JobQueue
from api.errors import APIError
from utils.logger import get_logger

logger = get_logger(__name__)

_PREFIX = "rag:ratelimit:"


class RateLimiter:
    def __init__(self, job_queue: JobQueue):
        self._queue = job_queue

    async def _redis(self):
        try:
            return await self._queue.connection()
        except APIError:
            logger.warning("Rate limits are off: Redis is not reachable")
            return None

    async def hit(self, key: str, limit: int, window_seconds: int) -> None:
        """Count one attempt; raise 429 once there were more than `limit` in the window."""
        redis = await self._redis()
        if redis is None:
            return
        name = _PREFIX + key
        count = await redis.incr(name)
        if count == 1:
            await redis.expire(name, window_seconds)
        if count > limit:
            raise _too_many(await redis.ttl(name))

    async def check(self, key: str, limit: int) -> None:
        """Raise 429 if `key` already reached `limit` (without counting this attempt)."""
        redis = await self._redis()
        if redis is None:
            return
        count = await redis.get(_PREFIX + key)
        if count and int(count) >= limit:
            raise _too_many(await redis.ttl(_PREFIX + key))

    async def reset(self, key: str) -> None:
        redis = await self._redis()
        if redis is not None:
            await redis.delete(_PREFIX + key)


def _too_many(seconds: int) -> APIError:
    seconds = max(int(seconds), 1)
    minutes = max(round(seconds / 60), 1)
    return APIError(429, "too_many_attempts",
                    f"Too many attempts. Please wait about {minutes} minute(s) and try again.",
                    details={"retry_after_seconds": seconds}, headers={"Retry-After": str(seconds)})
