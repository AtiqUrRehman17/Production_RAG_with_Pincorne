"""Conversations: save the question, answer it with the same RAGChain as the CLI, save the answer.

Earlier turns are read from the database, so follow-up questions work as in
`python main.py chat`. Each answer is one LangSmith trace; its run ID is saved
on the message (trace_id), so feedback and the logs can point to it.
"""

import time
from collections.abc import Callable

from langchain_core.documents import Document
from langsmith import uuid7
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.errors import APIError
from api.schemas.chat import ConversationOut, FeedbackOut, MessageOut, SourceOut
from database.engine import session
from database.models import Conversation, Document as DocumentRow, Message, new_id, utc_now
from llm.rag_chain import ChatTurn, RAGChain
from retrieval.citations import source_label
from retrieval.retriever import with_overrides
from utils.config import get_settings
from utils.exceptions import RAGError
from utils.request_context import current_request_id
from utils.tracing import tracing_enabled

_TITLE_CHARS = 80


# ---------------------------------------------------------------- output shapes
def source_out(number: int, passage: Document) -> SourceOut:
    meta = passage.metadata
    return SourceOut(
        number=number, label=source_label(meta), document_id=meta.get("document_id"),
        file_name=meta.get("file_name"), page_number=meta.get("page_number"), page_end=meta.get("page_end"),
        section=meta.get("section") or None, text=passage.page_content, score=meta.get("score"),
        embedding_score=meta.get("embedding_score"), score_type=meta.get("score_type"),
    )


def conversation_out(conversation: Conversation) -> ConversationOut:
    return ConversationOut(id=conversation.id, title=conversation.title, document_ids=conversation.document_ids,
                           created_at=conversation.created_at, updated_at=conversation.updated_at)


def message_out(message: Message) -> MessageOut:
    feedback = message.feedback
    return MessageOut(
        id=message.id, role=message.role, content=message.content, status=message.status,
        found=message.found, searched_for=message.searched_for, citations=message.citations,
        invalid_citations=message.invalid_citations, error=message.error, trace_id=message.trace_id,
        request_id=message.request_id, latency_ms=message.latency_ms, created_at=message.created_at,
        feedback=FeedbackOut(rating="up" if feedback.rating > 0 else "down", comment=feedback.comment,
                             updated_at=feedback.updated_at) if feedback else None,
    )


# ---------------------------------------------------------------- lookups
def get_conversation(db: Session, conversation_id: str, user_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    # Another user's conversation is "not found", so IDs can't be probed
    if conversation is None or conversation.user_id != user_id:
        raise APIError(404, "conversation_not_found", f"No conversation with ID {conversation_id} was found.")
    return conversation


def check_document_ids(db: Session, user_id: str, document_ids: list[str] | None) -> list[str] | None:
    """The documents a conversation or search is limited to; all must be the user's."""
    if not document_ids:
        return None
    document_ids = list(dict.fromkeys(document_ids))
    found = set(db.scalars(select(DocumentRow.document_id).where(
        DocumentRow.user_id == user_id, DocumentRow.document_id.in_(document_ids))))
    missing = [d for d in document_ids if d not in found]
    if missing:
        raise APIError(400, "unknown_document", "Some documents were not found.", details={"document_ids": missing})
    return document_ids


def history_turns(messages: list[Message]) -> list[ChatTurn]:
    """Earlier questions with their answers. Failed answers are left out."""
    turns = []
    for question, answer in zip(messages, messages[1:]):
        if question.role == "user" and answer.role == "assistant" and answer.status == "complete":
            turns.append(ChatTurn(question.content, answer.content))
    return turns


# ---------------------------------------------------------------- answering
def answer_question(
    conversation_id: str,
    user_id: str,
    question: str,
    no_rerank: bool = False,
    on_token: Callable[[str], None] | None = None,
    on_question_saved: Callable[[Message], None] | None = None,
) -> tuple[Message, Message]:
    """Save the question, answer it and save the answer. Blocking: run it in a thread.
    A failed answer is saved too (status "error"), then the error is raised."""
    with session() as db:
        conversation = get_conversation(db, conversation_id, user_id)
        history = history_turns(conversation.messages)
        document_ids = conversation.document_ids
        question_message = Message(conversation_id=conversation_id, role="user", content=question,
                                   request_id=current_request_id(), feedback=None)
        db.add(question_message)
        if not conversation.title:
            conversation.title = " ".join(question.split())[:_TITLE_CHARS]
        conversation.updated_at = utc_now()
        db.commit()
    if on_question_saved:
        on_question_saved(question_message)

    answer_message = Message(id=new_id(), conversation_id=conversation_id, role="assistant",
                             request_id=current_request_id(), feedback=None,
                             trace_id=str(uuid7()) if tracing_enabled() else None)
    started = time.perf_counter()
    try:
        chain = RAGChain(user_id, with_overrides(get_settings(), no_rerank=no_rerank), document_ids=document_ids)
        # thread_id groups a conversation's traces in LangSmith
        extra = {"metadata": {"thread_id": conversation_id, "message_id": answer_message.id, "user_id": user_id}}
        if answer_message.trace_id:
            extra["run_id"] = answer_message.trace_id
        answer = chain.ask(question, history=history, on_token=on_token, langsmith_extra=extra)
    except Exception as exc:
        answer_message.status = "error"
        answer_message.error = str(exc) if isinstance(exc, RAGError) else "Something went wrong while answering."
        _save(answer_message, started)
        raise

    answer_message.content = answer.text
    answer_message.found = answer.found
    answer_message.searched_for = answer.standalone_question if answer.standalone_question != question else None
    answer_message.citations = [source_out(c.number, c.passage).model_dump() for c in answer.citations]
    answer_message.invalid_citations = answer.invalid_citation_numbers
    _save(answer_message, started)
    return question_message, answer_message


def _save(message: Message, started: float) -> None:
    message.latency_ms = round((time.perf_counter() - started) * 1000)
    with session() as db:
        db.add(message)
        db.commit()
