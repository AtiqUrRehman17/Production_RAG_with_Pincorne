"""Chats with your documents: create, list, rename, delete, and ask questions.

Asking has two forms:
  POST .../messages         the whole answer at once
  POST .../messages/stream  the answer word by word (Server-Sent Events):
      event: question   the saved question (MessageOut)
      event: token      {"text": "..."} a piece of the answer
      event: answer     the saved answer with its citations (MessageOut)
      event: error      {"error": {...}} same format as other errors
"""

import asyncio
import json

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.dependencies import current_user_id, get_db
from api.errors import describe
from api.pagination import MAX_LIMIT, paginate
from api.schemas.chat import (
    AskRequest,
    AskResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
)
from api.schemas.common import Page
from api.services.chat import (
    answer_question,
    check_document_ids,
    conversation_out,
    get_conversation,
    message_out,
)
from database.models import Conversation, Message, utc_now
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# Answers that keep running after the browser disconnected (they are still saved)
_running: set[asyncio.Task] = set()


@router.post("", response_model=ConversationOut, status_code=201, summary="Start a new chat")
def create_conversation(body: ConversationCreate, user_id: str = Depends(current_user_id),
                        db: Session = Depends(get_db)) -> ConversationOut:
    conversation = Conversation(user_id=user_id, title=(body.title or "").strip(),
                                document_ids=check_document_ids(db, user_id, body.document_ids))
    db.add(conversation)
    db.commit()
    return conversation_out(conversation)


@router.get("", response_model=Page[ConversationOut], summary="Your chats, most recently used first")
def list_conversations(
    limit: int = Query(30, ge=1, le=MAX_LIMIT),
    cursor: str | None = None,
    user_id: str = Depends(current_user_id),
    db: Session = Depends(get_db),
) -> Page[ConversationOut]:
    query = select(Conversation).where(Conversation.user_id == user_id)
    rows, next_cursor = paginate(db, query, Conversation.updated_at, Conversation.id, limit, cursor)
    return Page(items=[conversation_out(row) for row in rows], next_cursor=next_cursor)


@router.get("/{conversation_id}", response_model=ConversationDetail, summary="A chat with all its messages")
def get_conversation_detail(conversation_id: str, user_id: str = Depends(current_user_id),
                            db: Session = Depends(get_db)) -> ConversationDetail:
    conversation = get_conversation(db, conversation_id, user_id)
    messages = db.scalars(select(Message).where(Message.conversation_id == conversation.id)
                          .options(selectinload(Message.feedback)).order_by(Message.created_at))
    return ConversationDetail(**conversation_out(conversation).model_dump(),
                              messages=[message_out(m) for m in messages])


@router.patch("/{conversation_id}", response_model=ConversationOut, summary="Rename a chat or change its documents")
def update_conversation(conversation_id: str, body: ConversationUpdate, user_id: str = Depends(current_user_id),
                        db: Session = Depends(get_db)) -> ConversationOut:
    conversation = get_conversation(db, conversation_id, user_id)
    if "title" in body.model_fields_set:
        conversation.title = (body.title or "").strip()
    if "document_ids" in body.model_fields_set:
        conversation.document_ids = check_document_ids(db, user_id, body.document_ids)
    conversation.updated_at = utc_now()
    db.commit()
    return conversation_out(conversation)


@router.delete("/{conversation_id}", status_code=204, summary="Delete a chat and its messages")
def delete_conversation(conversation_id: str, user_id: str = Depends(current_user_id),
                        db: Session = Depends(get_db)) -> Response:
    db.delete(get_conversation(db, conversation_id, user_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{conversation_id}/messages", response_model=AskResponse, summary="Ask a question (whole answer)")
def ask(conversation_id: str, body: AskRequest, user_id: str = Depends(current_user_id)) -> AskResponse:
    question, answer = answer_question(conversation_id, user_id, body.question.strip(), body.no_rerank)
    return AskResponse(question=message_out(question), answer=message_out(answer))


def _event(name: str, data) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{conversation_id}/messages/stream", summary="Ask a question (answer streamed word by word)",
             response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Events: question, token, answer, error"}})
async def ask_stream(conversation_id: str, body: AskRequest, user_id: str = Depends(current_user_id)):
    def check() -> None:
        from database.engine import session

        with session() as db:
            get_conversation(db, conversation_id, user_id)

    await asyncio.to_thread(check)  # a wrong ID is a normal 404, before the stream starts

    loop = asyncio.get_running_loop()
    events: asyncio.Queue = asyncio.Queue()

    def push(name: str, data) -> None:
        loop.call_soon_threadsafe(events.put_nowait, (name, data))

    def run() -> None:
        try:
            _, answer = answer_question(
                conversation_id, user_id, body.question.strip(), body.no_rerank,
                on_token=lambda text: push("token", {"text": text}),
                on_question_saved=lambda m: push("question", message_out(m).model_dump(mode="json")),
            )
            push("answer", message_out(answer).model_dump(mode="json"))
        except Exception as exc:
            status, error = describe(exc)
            if status >= 500 and error["error"]["code"] == "internal_error":
                logger.exception("Streaming answer failed")
            push("error", error)
        finally:
            push("end", None)

    async def stream():
        # Runs in a thread; keeps going (and saves the answer) even if the browser disconnects
        task = asyncio.create_task(asyncio.to_thread(run))
        _running.add(task)
        task.add_done_callback(_running.discard)
        while True:
            name, data = await events.get()
            if name == "end":
                break
            yield _event(name, data)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
