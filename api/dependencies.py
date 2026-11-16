"""Shared pieces endpoints ask for with Depends(...)."""

import asyncio
import secrets
from collections.abc import Iterator

from arq.connections import ArqRedis
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from accounts.security import read_access_token, token_matches_password
from accounts.service import get_user
from api.errors import APIError
from database.engine import session
from database.models import User
from utils.config import get_settings
from utils.logger import get_logger
from workers import queue

logger = get_logger(__name__)

# In /docs, the "Authorize" button asks for this token (from POST /api/v1/auth/login)
_bearer = HTTPBearer(auto_error=False, description="The access_token from /api/v1/auth/login")


def get_db() -> Iterator[Session]:
    with session() as db:
        yield db


def _user_from_token(credentials: HTTPAuthorizationCredentials | None) -> User:
    if credentials is None:
        raise APIError(401, "not_authenticated", "Please log in first.")
    claims = read_access_token(credentials.credentials, get_settings())
    user = get_user(claims["sub"])
    if user is None:
        raise APIError(401, "invalid_token", "Your login is not valid. Please log in again.")
    if not user.is_active:
        raise APIError(403, "account_disabled", "This account is disabled.")
    if not token_matches_password(claims, user):
        raise APIError(401, "token_revoked", "Your password was changed. Please log in again.")
    return user


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    """The logged-in user (from the Authorization: Bearer <access token> header)."""
    return _user_from_token(credentials)


def current_user_id(user: User = Depends(current_user)) -> str:
    """The logged-in user's ID: their documents, chats and jobs are stored under it
    (and their vectors in the Pinecone namespace of the same name)."""
    return user.id


def require_admin(
    x_admin_key: str | None = Header(None, description="ADMIN_API_KEY from .env (for scripts), "
                                                       "or log in as an admin instead"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """An admin account's login, or the ADMIN_API_KEY (for scripts and curl)."""
    if x_admin_key:
        expected = get_settings().admin_api_key
        if expected and expected.get_secret_value() and secrets.compare_digest(
                x_admin_key.encode(), expected.get_secret_value().encode()):
            return
        raise APIError(401, "unauthorized", "The X-Admin-Key is not valid.")
    if _user_from_token(credentials).role != "admin":
        raise APIError(403, "forbidden", "Only admins can use this.")


class JobQueue:
    """The connection to the Redis job queue, opened on first use (so the API
    starts even when Redis is down, and reconnects once it is back)."""

    def __init__(self):
        self._redis: ArqRedis | None = None
        self._lock = asyncio.Lock()

    async def connection(self) -> ArqRedis:
        if self._redis is None:
            async with self._lock:
                if self._redis is None:
                    try:
                        self._redis = await queue.connect(get_settings(), retries=1)
                    except Exception as exc:
                        logger.error("Redis is not reachable: %s", exc)
                        raise _queue_unavailable() from exc
        return self._redis

    async def enqueue(self, function: str, *args, job_id: str | None = None) -> None:
        redis = await self.connection()
        try:
            await redis.enqueue_job(function, *args, _job_id=job_id)
        except Exception as exc:
            logger.error("Could not add a %s job to the queue: %s", function, exc)
            raise _queue_unavailable() from exc

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


def _queue_unavailable() -> APIError:
    return APIError(503, "queue_unavailable",
                    "The background job queue (Redis) is not reachable. Start it with "
                    "'docker compose up -d redis' and try again.")


def get_queue(request: Request) -> JobQueue:
    return request.app.state.queue
