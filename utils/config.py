"""Central settings for the whole app, loaded once from the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Settings below are read into the Settings object, but LangSmith reads its own
# (LANGSMITH_TRACING, LANGSMITH_API_KEY, ...) from environment variables, so the
# .env file is also loaded into the environment. Variables already set in the
# environment win over .env, matching how Settings reads them.
load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM provider for answers and follow-up rewrites (embeddings always use Gemini)
    llm_provider: Literal["gemini", "groq"] = "gemini"
    llm_max_output_tokens: int = Field(2048, gt=0)

    # Groq
    groq_api_key: SecretStr | None = None
    groq_llm_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = Field(0.1, ge=0, le=2)

    # Gemini
    gemini_api_key: SecretStr
    gemini_llm_model: str = "gemini-3.5-flash"
    llm_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = 768
    embedding_batch_size: int = Field(100, gt=0, le=100)

    # Pinecone
    pinecone_api_key: SecretStr
    pinecone_index_name: str = "rag-documents"
    pinecone_metric: str = "cosine"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    # User (CLI mode)
    default_user_id: str = "local-user"

    # File validation
    allowed_extensions: str = "pdf,txt,docx"
    max_file_size_mb: float = Field(50, gt=0)
    max_pdf_pages: int = Field(500, gt=0)
    min_text_chars_per_page: int = Field(50, ge=0)

    # Local storage
    upload_dir: Path = Path("data/uploads")
    # The earlier JSON registry; its documents are imported into the database once
    document_registry_path: Path = Path("data/documents.json")

    # Chunking
    chunk_size: int = Field(800, gt=0)
    chunk_overlap: int = Field(100, ge=0)
    min_chunk_size: int = Field(50, ge=0)

    # Retrieval
    top_k: int = Field(5, gt=0)
    min_relevance_score: float = Field(0.55, ge=0, le=1)
    relative_score_margin: float = Field(0.1, ge=0, le=1)

    # Reranking
    reranker_enabled: bool = True
    rerank_model: str = "bge-reranker-v2-m3"
    retrieval_fetch_k: int = Field(20, gt=0, le=100)  # the model accepts at most 100 documents
    rerank_top_n: int = Field(8, gt=0)
    rerank_min_score: float = Field(0.2, ge=0, le=1)
    rerank_min_best_score: float = Field(0.02, ge=0, le=1)

    # Chat
    chat_history_turns: int = Field(5, ge=0)

    # Evaluation
    eval_user_id: str = "eval"
    eval_dataset_path: Path = Path("evaluation/datasets/golden_v1.json")
    eval_results_dir: Path = Path("evaluation/results")

    # AI judge (RAGAS): grades answers by meaning; runs on Groq, separately from the answer model
    judge_model: str = "qwen/qwen3.8-27b"
    # Sent to Groq as reasoning_effort ("none" turns thinking off for Qwen; gpt-oss uses low/medium/high)
    judge_reasoning_effort: str | None = "none"
    judge_metrics: str = "faithfulness,answer_relevancy,context_precision,context_recall"
    # DeepEval checks (--deepeval); they use the same judge model
    deepeval_metrics: str = "correctness,citation_quality,completeness,contextual_relevancy"
    # A DeepEval score at or above this counts as a pass for that check
    deepeval_threshold: float = Field(0.7, ge=0, le=1)

    # Backend (FastAPI): python -m api
    api_host: str = "127.0.0.1"
    api_port: int = Field(8000, gt=0, lt=65536)
    # Web pages allowed to call the API from a browser (the React dev server)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # For scripts: opens the /api/v1/admin endpoints without logging in (admins can also log in)
    admin_api_key: SecretStr | None = None
    # Jobs, conversations, feedback, logs and the document registry
    database_url: str = "sqlite:///data/app.db"
    # Uploads wait here until the worker has ingested them
    incoming_dir: Path = Path("data/incoming")

    # Background worker: python -m workers
    redis_url: str = "redis://127.0.0.1:6379/0"
    worker_max_jobs: int = Field(2, gt=0)  # jobs one worker runs at the same time

    # App logs saved to the database (shown by /api/v1/admin/logs)
    log_db_level: str = "INFO"
    log_retention_days: int = Field(14, gt=0)

    # Accounts: signs the login tokens; the API refuses to start without it (32+ characters)
    jwt_secret: SecretStr | None = None
    access_token_minutes: int = Field(15, gt=0, le=24 * 60)  # how long a login token works
    refresh_token_days: int = Field(7, gt=0, le=90)  # how long you stay logged in without using the app
    registration_open: bool = True  # false: nobody can create a new account
    # true when the site runs on HTTPS (production): the login cookie is then never sent unencrypted
    auth_cookie_secure: bool = False

    @model_validator(mode="after")
    def _check_values(self) -> "Settings":
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise ValueError("LLM_PROVIDER is groq, so GROQ_API_KEY must be set")
        if self.embedding_dimension not in (768, 1536, 3072):
            raise ValueError("EMBEDDING_DIMENSION must be 768, 1536 or 3072")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.min_chunk_size >= self.chunk_size:
            raise ValueError("MIN_CHUNK_SIZE must be smaller than CHUNK_SIZE")
        if self.rerank_min_best_score > self.rerank_min_score:
            raise ValueError("RERANK_MIN_BEST_SCORE must not be higher than RERANK_MIN_SCORE")
        if self.retrieval_fetch_k < max(self.top_k, self.rerank_top_n):
            raise ValueError("RETRIEVAL_FETCH_K must be at least TOP_K and RERANK_TOP_N")
        # Relative paths are resolved from the project root, not the current folder
        for name in ("upload_dir", "document_registry_path", "eval_dataset_path", "eval_results_dir",
                     "incoming_dir"):
            path = getattr(self, name)
            if not path.is_absolute():
                setattr(self, name, PROJECT_ROOT / path)
        sqlite_prefix = "sqlite:///"
        if self.database_url.startswith(sqlite_prefix):
            path = Path(self.database_url.removeprefix(sqlite_prefix))
            if not path.is_absolute():
                self.database_url = sqlite_prefix + (PROJECT_ROOT / path).as_posix()
        return self

    @property
    def llm_model(self) -> str:
        """The model that writes answers, for the active LLM_PROVIDER."""
        return self.groq_llm_model if self.llm_provider == "groq" else self.gemini_llm_model

    @property
    def allowed_extension_set(self) -> set[str]:
        return {
            ext.strip().lower().lstrip(".")
            for ext in self.allowed_extensions.split(",")
            if ext.strip()
        }

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.max_file_size_mb * 1024 * 1024)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
