from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(None, max_length=200, description="Defaults to the first question")
    document_ids: list[str] | None = Field(None, description="Only use these documents (default: all)")


class ConversationUpdate(BaseModel):
    title: str | None = Field(None, max_length=200)
    document_ids: list[str] | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    document_ids: list[str] | None
    created_at: datetime
    updated_at: datetime


class SourceOut(BaseModel):
    """A passage of a document: a citation of an answer, or a search result."""

    number: int
    label: str  # e.g. "handbook.pdf, pages 4-6 (Leave Policy > Sick Leave)"
    document_id: str | None
    file_name: str | None
    page_number: int | None
    page_end: int | None
    section: str | None
    text: str
    score: float | None = None
    embedding_score: float | None = None
    score_type: str | None = None


class FeedbackIn(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None = Field(None, max_length=2000)


class FeedbackOut(BaseModel):
    rating: Literal["up", "down"]
    comment: str | None
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["complete", "error"]
    found: bool | None = None  # False: the documents don't answer the question
    searched_for: str | None = None  # the follow-up question rewritten to stand alone
    citations: list[SourceOut] | None = None
    invalid_citations: list[int] | None = None  # cited numbers that match no source
    error: str | None = None
    trace_id: str | None = None  # LangSmith run ID (see /api/v1/admin/traces/{trace_id})
    request_id: str | None = None
    latency_ms: int | None = None
    created_at: datetime
    feedback: FeedbackOut | None = None


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    no_rerank: bool = Field(False, description="Rank by embedding scores only (for comparison)")


class AskResponse(BaseModel):
    question: MessageOut
    answer: MessageOut


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    document_ids: list[str] | None = None
    top_k: int | None = Field(None, ge=1, le=50, description="Most passages to return")
    no_rerank: bool = False


class SearchResponse(BaseModel):
    question: str
    ranking: str  # "reranker <model>" or "embedding scores only"
    passages: list[SourceOut]
