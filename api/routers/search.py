"""Retrieval only: which passages would be used to answer a question (like `python main.py search`)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import current_user_id, get_db
from api.schemas.chat import SearchRequest, SearchResponse
from api.services.chat import check_document_ids, source_out
from retrieval.retriever import DocumentRetriever, with_overrides
from utils.config import get_settings

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse, summary="Find the passages most relevant to a question")
def search(body: SearchRequest, user_id: str = Depends(current_user_id), db: Session = Depends(get_db)) -> SearchResponse:
    settings = with_overrides(get_settings(), body.no_rerank, body.top_k)
    document_ids = check_document_ids(db, user_id, body.document_ids)
    passages = DocumentRetriever.for_user(user_id, settings, document_ids).invoke(
        body.question, config={"metadata": {"user_id": user_id}})
    ranking = f"reranker {settings.rerank_model}" if settings.reranker_enabled else "embedding scores only"
    return SearchResponse(question=body.question, ranking=ranking,
                          passages=[source_out(i, p) for i, p in enumerate(passages, start=1)])
