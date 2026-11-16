"""LangSmith tracing helpers.

LangSmith reads its settings (LANGSMITH_TRACING, LANGSMITH_API_KEY,
LANGSMITH_PROJECT, LANGSMITH_ENDPOINT) from environment variables;
utils/config.py loads .env into the environment so they are found.

LangChain parts (prompt templates, Gemini calls, the retriever) are traced
automatically. `traced` marks our own steps (the whole question, the reranker,
ingestion) so they show up as named steps in the same trace tree.
Tracing only records what happens; it never changes results.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

# Must come first: importing the settings loads .env into the environment, and
# LangSmith caches its settings the first time it reads them
import utils.config  # noqa: F401

from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import traceable
from langsmith.run_helpers import get_tracing_context, tracing_context
from langsmith.utils import tracing_is_enabled

# Our steps are marked with this; with LANGSMITH_TRACING=false it does nothing
traced = traceable


def tracing_enabled() -> bool:
    return bool(tracing_is_enabled())


def tracing_project() -> str:
    return os.environ.get("LANGSMITH_PROJECT", "default")


@contextmanager
def trace_scope(tags: list[str] | None = None, metadata: dict | None = None) -> Iterator[None]:
    """Add tags and metadata to every step traced inside the block.

    LangSmith's own tracing_context replaces the outer tags and metadata, so
    they are merged here: an inner scope (e.g. one evaluation question) keeps
    the outer one's labels (e.g. the `evaluate` command tag).
    """
    current = get_tracing_context()
    merged_tags = sorted(set(current.get("tags") or []) | set(tags or []))
    merged_metadata = {**(current.get("metadata") or {}), **(metadata or {})}
    with tracing_context(tags=merged_tags, metadata=merged_metadata):
        yield


def model_labels(settings) -> dict:
    """Trace metadata naming the models and settings that produced an answer."""
    return {
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_thinking_level": settings.llm_thinking_level if settings.llm_provider == "gemini" else "n/a",
        "embedding_model": settings.gemini_embedding_model,
        "reranker": settings.rerank_model if settings.reranker_enabled else "off",
        "app_env": settings.app_env,
    }


def flush_traces() -> None:
    """Send any traces still queued. A CLI command ends quickly, and traces
    are sent in the background, so without this the last ones could be lost."""
    try:
        wait_for_all_tracers()
    except Exception:  # never let tracing problems break the app
        pass


def text_preview(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."
