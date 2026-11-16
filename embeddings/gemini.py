"""Gemini embeddings as a LangChain `Embeddings` class.

Wraps LangChain's GoogleGenerativeAIEmbeddings and adds what it lacks:
  - retries on rate limits (429), server errors and network failures, so one
    hiccup doesn't fail a whole upload. On a 429 it waits as long as Gemini says
    ("retry in 32s"): the free tier allows 100 requests and 30,000 tokens per
    minute, so a large document is embedded over several minutes, batch by batch
  - L2 normalization (Google recommends it for 768/1536-dim vectors)
  - a dimension check, so a wrong setting can't write bad vectors to Pinecone

Documents are embedded with task type RETRIEVAL_DOCUMENT and questions with
RETRIEVAL_QUERY (the defaults of the wrapped class), which improves search.
"""

import logging
import math
import re
from functools import lru_cache

import httpx
from google.genai import errors as genai_errors
from langchain_core.embeddings import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tenacity import (
    RetryCallState,
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from utils.config import Settings, get_settings
from utils.exceptions import EmbeddingError
from utils.logger import get_logger

logger = get_logger(__name__)

_MAX_ATTEMPTS = 8  # per batch; with per-minute limits that is several minutes of waiting
_MAX_SERVER_WAIT_SECONDS = 90
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
# "Please retry in 32.79s." in the message, or 'retryDelay': '32s' in the details
_RETRY_DELAY = re.compile(r"retry in ([\d.]+)\s*s|retryDelay'?\"?\s*:\s*'?\"?([\d.]+)s")

_backoff = wait_exponential_jitter(initial=2, max=60)


def _is_retryable(exc: BaseException) -> bool:
    # LangChain wraps SDK errors, so look at the original cause too
    for error in (exc, exc.__cause__):
        if isinstance(error, genai_errors.APIError) and error.code in _RETRYABLE_STATUS_CODES:
            return True
        if isinstance(error, (httpx.TransportError, TimeoutError, ConnectionError)):
            return True
    return False


def _is_rate_limit(exc: BaseException) -> bool:
    return any(isinstance(error, genai_errors.APIError) and error.code == 429 for error in (exc, exc.__cause__))


def _wait_up_to(max_seconds: float):
    def wait(retry_state: RetryCallState) -> float:
        """As long as Gemini asks after a 429 (plus a second), otherwise exponential backoff."""
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        if exc is not None and _is_rate_limit(exc):
            match = _RETRY_DELAY.search(f"{exc} {exc.__cause__}")
            if match:
                return min(float(match.group(1) or match.group(2)) + 1, max_seconds)
            return min(max(_backoff(retry_state), 15), max_seconds)
        return min(_backoff(retry_state), max_seconds)
    return wait


def _retrying(attempts: int, max_wait_seconds: float):
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(attempts),
        wait=_wait_up_to(max_wait_seconds),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# Uploads run in the background and may wait for the per-minute limit to reset;
# a question has someone waiting for the answer
_with_retry = _retrying(_MAX_ATTEMPTS, _MAX_SERVER_WAIT_SECONDS)
_with_quick_retry = _retrying(3, 10)


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


class GeminiEmbeddings(Embeddings):
    def __init__(self, settings: Settings):
        self.dimension = settings.embedding_dimension
        self.batch_size = settings.embedding_batch_size
        self.model_name = settings.gemini_embedding_model
        self._client = GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.gemini_api_key,
            output_dimensionality=settings.embedding_dimension,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        # One batch at a time so a retry only repeats the failed batch
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            vectors.extend(self._call(self._embed_batch, batch))
            logger.info("Embedded %d/%d chunks", len(vectors), len(texts))

        if len(vectors) != len(texts):
            raise EmbeddingError(f"Expected {len(texts)} embeddings, got {len(vectors)}.")
        return [self._check(_normalize(v)) for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self._check(_normalize(self._call(self._embed_query, text)))

    @_with_retry
    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        return self._client.embed_documents(batch, batch_size=self.batch_size)

    @_with_quick_retry
    def _embed_query(self, text: str) -> list[float]:
        return self._client.embed_query(text)

    @staticmethod
    def _call(func, arg):
        try:
            return func(arg)
        except Exception as exc:
            logger.error("Embedding request failed: %s", exc.__cause__ or exc)
            logger.debug("Embedding failure details", exc_info=True)
            if _is_rate_limit(exc):
                raise EmbeddingError(
                    "Gemini's embedding limit was reached (the free tier allows 100 requests and 30,000 "
                    "tokens per minute, and a daily amount). Try again in a few minutes."
                ) from exc
            raise EmbeddingError(
                "Could not create embeddings with Gemini. "
                "Check GEMINI_API_KEY, your quota and your internet connection."
            ) from exc

    def _check(self, vector: list[float]) -> list[float]:
        if len(vector) != self.dimension:
            raise EmbeddingError(
                f"Gemini returned {len(vector)}-dim vectors but EMBEDDING_DIMENSION is "
                f"{self.dimension}. They must match the Pinecone index."
            )
        return vector


@lru_cache
def get_embeddings() -> GeminiEmbeddings:
    return GeminiEmbeddings(get_settings())
