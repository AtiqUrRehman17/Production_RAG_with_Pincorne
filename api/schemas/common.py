from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None  # pass as ?cursor= to get the next page; None = last page


# Shown in /docs for every endpoint
ERROR_RESPONSES: dict[int | str, dict] = {
    "4XX": {"model": ErrorResponse, "description": "The request could not be handled"},
    "5XX": {"model": ErrorResponse, "description": "A server or upstream service problem"},
}
