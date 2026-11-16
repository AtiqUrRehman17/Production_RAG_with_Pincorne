"""Is the server alive, and can it reach everything it needs?"""

import asyncio
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.dependencies import JobQueue, get_queue
from api.schemas.admin import CheckOut, HealthOut, ReadyOut
from database.engine import session
from database.models import utc_now
from utils.config import get_settings
from utils.tracing import tracing_enabled
from workers.queue import worker_health_key

router = APIRouter(prefix="/health", tags=["health"])

API_VERSION = "1.0.0"
_CHECK_SECONDS = 10


@router.get("", response_model=HealthOut, summary="The server is running")
def health() -> HealthOut:
    return HealthOut(status="ok", version=API_VERSION, time=utc_now())


def _check_database() -> CheckOut:
    with session() as db:
        db.execute(text("SELECT 1"))
    return CheckOut(ok=True)


def _check_pinecone() -> CheckOut:
    from vectordb.pinecone_store import get_store

    get_store().index.describe_index_stats()
    return CheckOut(ok=True, detail=get_settings().pinecone_index_name)


async def _run_check(check) -> CheckOut:
    try:
        return await asyncio.wait_for(check(), _CHECK_SECONDS)
    except TimeoutError:
        return CheckOut(ok=False, detail="no answer in time")
    except Exception as exc:
        return CheckOut(ok=False, detail=" ".join(str(exc).split())[:200] or type(exc).__name__)


@router.get("/ready", response_model=ReadyOut, summary="Database, Redis, the worker and Pinecone are reachable",
            responses={503: {"model": ReadyOut, "description": "Something the API needs is not reachable"}})
async def ready(queue: JobQueue = Depends(get_queue)):
    async def redis() -> CheckOut:
        await (await queue.connection()).ping()
        return CheckOut(ok=True)

    async def worker() -> CheckOut:
        alive = await (await queue.connection()).exists(worker_health_key())
        return CheckOut(ok=bool(alive), detail=None if alive else "no worker is running (python -m workers)")

    names = ("database", "redis", "worker", "pinecone")
    results = await asyncio.gather(
        _run_check(lambda: asyncio.to_thread(_check_database)), _run_check(redis), _run_check(worker),
        _run_check(lambda: asyncio.to_thread(_check_pinecone)),
    )
    checks = dict(zip(names, results))
    checks["langsmith"] = CheckOut(ok=tracing_enabled() and bool(os.environ.get("LANGSMITH_API_KEY")),
                                   detail=None if tracing_enabled() else "tracing is off")
    settings = get_settings()
    api_keys = {
        "GEMINI_API_KEY": bool(settings.gemini_api_key.get_secret_value()),
        "PINECONE_API_KEY": bool(settings.pinecone_api_key.get_secret_value()),
        "GROQ_API_KEY": bool(settings.groq_api_key and settings.groq_api_key.get_secret_value()),
        "LANGSMITH_API_KEY": bool(os.environ.get("LANGSMITH_API_KEY")),
        "ADMIN_API_KEY": bool(settings.admin_api_key and settings.admin_api_key.get_secret_value()),
        "JWT_SECRET": bool(settings.jwt_secret and settings.jwt_secret.get_secret_value()),
    }
    # LangSmith and the worker are reported, but the API can answer questions without them
    ok = all(checks[name].ok for name in ("database", "redis", "pinecone"))
    body = ReadyOut(status="ready" if ok else "not_ready", checks=checks, api_keys=api_keys)
    return JSONResponse(status_code=200 if ok else 503, content=body.model_dump(mode="json"))
