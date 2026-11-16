"""The FastAPI app.  Start it with:  python -m api   (interactive docs: http://127.0.0.1:8000/docs)

Every endpoint is under /api/v1. The API is a thin layer: the work is done by
the same modules as the CLI (ingestion, retrieval, llm, evaluation); slow work
(uploads, deletes, evaluations) is handed to the background worker.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Must come first: importing the settings loads .env, which LangSmith reads once
from utils.config import get_settings  # noqa: I001

from accounts.security import check_secret
from api.dependencies import JobQueue
from api.errors import register_error_handlers
from api.middleware import RequestContextMiddleware
from api.routers import (
    admin_evaluations,
    admin_monitoring,
    auth,
    conversations,
    documents,
    feedback,
    health,
    jobs,
    search,
)
from api.schemas.common import ERROR_RESPONSES
from database.engine import get_engine
from database.log_handler import disable_database_logging, enable_database_logging
from utils.logger import get_logger
from utils.tracing import flush_traces, tracing_enabled, tracing_project

logger = get_logger(__name__)

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_secret(get_settings())  # no logins without JWT_SECRET: stop now, with a clear message
    enable_database_logging("api")
    get_engine()  # create the tables now, not during the first request
    app.state.queue = JobQueue()
    settings = get_settings()
    logger.info("API started (%s, answers by %s %s, tracing %s)", settings.app_env, settings.llm_provider,
                settings.llm_model, f"on: project '{tracing_project()}'" if tracing_enabled() else "off")
    yield
    await app.state.queue.close()
    flush_traces()
    logger.info("API stopped")
    disable_database_logging()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG API",
        description="Chat with your documents: upload PDF, DOCX and TXT files and get answers with citations.",
        version=health.API_VERSION,
        lifespan=lifespan,
        responses=ERROR_RESPONSES,
    )
    app.add_middleware(RequestContextMiddleware)
    # Added last, so it runs first: browsers get CORS headers even on errors
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,  # lets the browser send the login cookie to /auth/refresh
        expose_headers=["X-Request-ID"],
    )
    register_error_handlers(app)
    for module in (health, auth, documents, jobs, conversations, search, feedback, admin_monitoring,
                   admin_evaluations):
        app.include_router(module.router, prefix=API_PREFIX)
    return app


app = create_app()
