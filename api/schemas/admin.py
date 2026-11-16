from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CheckOut(BaseModel):
    ok: bool
    detail: str | None = None


class HealthOut(BaseModel):
    status: str
    version: str
    time: datetime


class ReadyOut(BaseModel):
    status: str  # "ready" | "not_ready"
    checks: dict[str, CheckOut]
    api_keys: dict[str, bool]  # which keys are set (never their values)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    level: str
    logger: str
    message: str
    exception: str | None
    request_id: str | None
    source: str


class TraceSummary(BaseModel):
    id: str
    name: str
    status: str | None
    error: str | None
    start_time: datetime
    end_time: datetime | None
    latency_seconds: float | None
    total_tokens: int | None
    tags: list[str]
    request_id: str | None
    conversation_id: str | None
    question: str | None
    url: str | None  # open the trace in LangSmith


class TraceStep(BaseModel):
    id: str
    name: str
    run_type: str
    status: str | None
    error: str | None
    start_time: datetime
    latency_seconds: float | None
    total_tokens: int | None
    inputs: Any
    outputs: Any
    steps: list["TraceStep"]


class TraceDetail(TraceSummary):
    metadata: dict
    inputs: Any
    outputs: Any
    steps: list[TraceStep]


class StatsOut(BaseModel):
    hours: int
    questions: dict[str, Any]
    feedback: dict[str, int]
    jobs: dict[str, int]
    logs: dict[str, int]
    recent_errors: list[LogOut]


class EvaluationRequest(BaseModel):
    saved_run: str | None = Field(None, description="Only grade this saved run (tag) with the judges; "
                                                    "no new answers")
    retrieval_only: bool = False
    no_rerank: bool = False
    tag: str | None = Field(None, pattern=r"^[A-Za-z0-9_-]{1,40}$")
    ids: list[str] | None = Field(None, description="Only these question ids")
    limit: int | None = Field(None, gt=0)
    ragas: bool = False
    ragas_metrics: list[str] | None = None
    deepeval: bool = False
    deepeval_metrics: list[str] | None = None


class EvaluationSummary(BaseModel):
    tag: str
    file: str
    dataset: str
    mode: str
    started_at: str
    duration_seconds: float | None
    questions: int
    passed: dict | None
    judges: list[str]
