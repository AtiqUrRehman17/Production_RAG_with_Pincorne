"""Thumbs up / down on an answer. Saved here and copied to the answer's LangSmith trace
(by the worker), so feedback appears next to the trace it is about."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from api.dependencies import JobQueue, current_user_id, get_db, get_queue
from api.errors import APIError
from api.schemas.chat import FeedbackIn, FeedbackOut
from database.models import Feedback, Message, utc_now
from utils.logger import get_logger
from utils.tracing import tracing_enabled
from workers import queue

logger = get_logger(__name__)

router = APIRouter(prefix="/messages", tags=["feedback"])


def _get_answer(db: Session, message_id: str, user_id: str) -> Message:
    message = db.get(Message, message_id)
    if message is None or message.conversation.user_id != user_id:
        raise APIError(404, "message_not_found", f"No message with ID {message_id} was found.")
    if message.role != "assistant" or message.status != "complete":
        raise APIError(400, "not_an_answer", "Feedback can only be given on a completed answer.")
    return message


async def _send_to_langsmith(job_queue: JobQueue, message: Message, feedback_id: str, delete: bool = False) -> None:
    """Best effort: the feedback is saved even if it can't be copied to LangSmith now."""
    if not (message.trace_id and tracing_enabled()):
        return
    try:
        await job_queue.enqueue(queue.FEEDBACK, feedback_id, delete)
    except APIError:
        logger.warning("Feedback %s was saved but not sent to LangSmith (queue unavailable)", feedback_id)


@router.post("/{message_id}/feedback", response_model=FeedbackOut, summary="Give or change feedback on an answer")
async def give_feedback(message_id: str, body: FeedbackIn, user_id: str = Depends(current_user_id),
                        db: Session = Depends(get_db), job_queue: JobQueue = Depends(get_queue)) -> FeedbackOut:
    message = _get_answer(db, message_id, user_id)
    feedback = message.feedback or Feedback(message_id=message.id, user_id=user_id)
    feedback.rating = 1 if body.rating == "up" else -1
    feedback.comment = (body.comment or "").strip() or None
    feedback.updated_at = utc_now()
    db.add(feedback)
    db.commit()
    await _send_to_langsmith(job_queue, message, feedback.id)
    return FeedbackOut(rating=body.rating, comment=feedback.comment, updated_at=feedback.updated_at)


@router.delete("/{message_id}/feedback", status_code=204, summary="Remove your feedback from an answer")
async def remove_feedback(message_id: str, user_id: str = Depends(current_user_id),
                          db: Session = Depends(get_db), job_queue: JobQueue = Depends(get_queue)) -> Response:
    message = _get_answer(db, message_id, user_id)
    feedback = message.feedback
    if feedback is not None:
        sent = feedback.sent_to_langsmith
        db.delete(feedback)
        db.commit()
        if sent:
            await _send_to_langsmith(job_queue, message, feedback.id, delete=True)
    return Response(status_code=204)
