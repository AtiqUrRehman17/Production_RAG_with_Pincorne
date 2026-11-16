"""Database tables.

  documents      every ingested document (the document registry)
  jobs           background work: ingest, delete, evaluation
  conversations  chats, and the messages in them
  messages       questions and answers, with citations and the LangSmith trace ID
  feedback       thumbs up / down on an answer
  app_logs       log lines from the API and the worker
  users          accounts (email, password hash, role)
  refresh_tokens logins that can get new access tokens (one per device)

Every table that belongs to a user has user_id: an account's ID (users.id), or
a plain name such as "local-user" / "eval" for data made with the CLI.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    """Stored as UTC, always returned with the UTC timezone (SQLite forgets it)."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("user_id", "sha256"),)

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    chunk_count: Mapped[int] = mapped_column(Integer)
    stored_path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(20))  # ingest | delete | evaluation | transfer
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued | processing | done | failed
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str | None] = mapped_column(String(64))  # the request that created the job
    file_name: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str | None] = mapped_column(String(64))
    document_id: Mapped[str | None] = mapped_column(String(36))
    params: Mapped[dict] = mapped_column(JSON, default=dict)  # what the job needs to run
    progress: Mapped[dict | None] = mapped_column(JSON)  # {"done": 3, "total": 45}
    result: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    document_ids: Mapped[list | None] = mapped_column(JSON)  # None = all of the user's documents
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="complete")  # complete | error
    # Answers only
    found: Mapped[bool | None] = mapped_column(Boolean)
    searched_for: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSON)
    invalid_citations: Mapped[list | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(36))  # LangSmith run ID of the answer
    request_id: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    feedback: Mapped["Feedback | None"] = relationship(
        back_populates="message", cascade="all, delete-orphan", uselist=False,
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1 = thumbs up, -1 = thumbs down
    comment: Mapped[str | None] = mapped_column(Text)
    sent_to_langsmith: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)

    message: Mapped[Message] = relationship(back_populates="feedback")


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, index=True)
    level: Mapped[str] = mapped_column(String(10))
    level_number: Mapped[int] = mapped_column(Integer, index=True)
    logger: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    exception: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(10))  # api | worker


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True)  # stored lowercase
    name: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(String(255))  # Argon2; the password itself is never stored
    role: Mapped[str] = mapped_column(String(10), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Login tokens made before this moment stop working (set when the password changes)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)


class RefreshToken(Base):
    """A login on one device. Only a hash of the token is stored; each use replaces
    it with a new one, and reusing an old one ends every login of that device."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)  # all tokens of one login
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
