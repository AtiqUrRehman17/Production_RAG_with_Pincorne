"""Accounts: register, log in, stay logged in, change password, delete, move data.

Plain functions without HTTP code, so the API, the worker and the CLI share them.
Every message in an AuthError is safe to show to the user.
"""

import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, update

from accounts.security import hash_password, hash_token, needs_rehash, new_refresh_token, verify_password
from database.engine import session
from database.models import Conversation, Document, Feedback, Job, RefreshToken, User, utc_now
from ingestion.registry import DocumentRegistry
from utils.config import Settings
from utils.exceptions import AuthError
from utils.logger import get_logger
from vectordb.pinecone_store import get_store

logger = get_logger(__name__)

MIN_PASSWORD_CHARS = 8
MAX_PASSWORD_CHARS = 128
_INVALID_LOGIN = "The email or password is wrong."


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_password_rules(password: str, email: str) -> None:
    if not MIN_PASSWORD_CHARS <= len(password) <= MAX_PASSWORD_CHARS:
        raise AuthError(f"The password must be {MIN_PASSWORD_CHARS} to {MAX_PASSWORD_CHARS} characters long.",
                        "weak_password", 422)
    if not password.strip() or password.strip().lower() == normalize_email(email):
        raise AuthError("Choose a password that is not your email address.", "weak_password", 422)


# ---------------------------------------------------------------- users
def get_user(user_id: str) -> User | None:
    with session() as db:
        return db.get(User, user_id)


def find_user(email: str) -> User | None:
    with session() as db:
        return db.scalar(select(User).where(User.email == normalize_email(email)))


def count_users() -> int:
    with session() as db:
        return db.scalar(select(func.count()).select_from(User))


def list_users() -> list[User]:
    with session() as db:
        return list(db.scalars(select(User).order_by(User.created_at)))


def register(email: str, password: str, name: str, settings: Settings) -> User:
    if not settings.registration_open:
        raise AuthError("New accounts can't be created right now.", "registration_closed", 403)
    email = normalize_email(email)
    check_password_rules(password, email)
    with session() as db:
        if db.scalar(select(User.id).where(User.email == email)):
            raise AuthError("An account with this email already exists. Log in instead.", "email_taken", 409)
        user = User(email=email, name=name.strip(), password_hash=hash_password(password))
        db.add(user)
        db.commit()
    logger.info("Account %s registered", user.id)
    return user


def authenticate(email: str, password: str) -> User:
    """The user with this email and password, or AuthError (the same message for a wrong
    email and a wrong password, so nobody can find out which emails have accounts)."""
    user = find_user(email)
    if not verify_password(user.password_hash if user else None, password):
        raise AuthError(_INVALID_LOGIN, "invalid_credentials")
    if not user.is_active:
        raise AuthError("This account is disabled.", "account_disabled", 403)
    with session() as db:
        user = db.get(User, user.id)
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = utc_now()
        db.commit()
    return user


def update_name(user_id: str, name: str) -> User:
    with session() as db:
        user = db.get(User, user_id)
        user.name, user.updated_at = name.strip(), utc_now()
        db.commit()
        return user


def change_password(user_id: str, current_password: str, new_password: str) -> User:
    """Set a new password. Every login (all devices) ends; the caller logs this device in again."""
    with session() as db:
        user = db.get(User, user_id)
        if not verify_password(user.password_hash, current_password):
            raise AuthError("The current password is wrong.", "wrong_password", 403)
        check_password_rules(new_password, user.email)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = user.updated_at = utc_now()
        db.commit()
    revoke_all_refresh_tokens(user_id)
    logger.info("Account %s changed its password; all logins ended", user_id)
    return user


def set_role(email: str, role: str) -> User:
    with session() as db:
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if user is None:
            raise AuthError(f"No account with the email {email}.", "user_not_found", 404)
        user.role, user.updated_at = role, utc_now()
        db.commit()
        return user


# ---------------------------------------------------------------- refresh tokens
def issue_refresh_token(user_id: str, settings: Settings, family_id: str | None = None,
                        user_agent: str | None = None, ip: str | None = None) -> str:
    token, token_hash = new_refresh_token()
    with session() as db:
        db.add(RefreshToken(user_id=user_id, token_hash=token_hash, family_id=family_id or str(uuid.uuid4()),
                            expires_at=utc_now() + timedelta(days=settings.refresh_token_days),
                            user_agent=(user_agent or "")[:255] or None, ip=ip))
        db.commit()
    return token


def rotate_refresh_token(token: str, settings: Settings, user_agent: str | None = None,
                         ip: str | None = None) -> tuple[User, str]:
    """Swap a refresh token for a new one. An old (already swapped) token being used again
    means it was copied: every token of that login is then cancelled."""
    expired = AuthError("Your session ended. Please log in again.", "session_expired")
    with session() as db:
        stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
        if stored is None:
            raise expired
        if stored.revoked_at is not None:
            db.execute(update(RefreshToken).where(RefreshToken.family_id == stored.family_id,
                                                  RefreshToken.revoked_at.is_(None)).values(revoked_at=utc_now()))
            db.commit()
            logger.warning("A used refresh token was presented again for account %s; that login was ended",
                           stored.user_id)
            raise expired
        if stored.expires_at <= utc_now():
            raise expired
        user = db.get(User, stored.user_id)
        if user is None or not user.is_active:
            raise expired
        stored.revoked_at = utc_now()
        family_id = stored.family_id
        db.commit()
    return user, issue_refresh_token(user.id, settings, family_id, user_agent, ip)


def revoke_refresh_token(token: str) -> None:
    """Log out this device: its whole login (token family) ends."""
    with session() as db:
        stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(token)))
        if stored is not None:
            db.execute(update(RefreshToken).where(RefreshToken.family_id == stored.family_id,
                                                  RefreshToken.revoked_at.is_(None)).values(revoked_at=utc_now()))
            db.commit()


def revoke_all_refresh_tokens(user_id: str) -> None:
    with session() as db:
        db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
                   .values(revoked_at=utc_now()))
        # Old ones are no longer needed
        db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id,
                                              RefreshToken.expires_at < utc_now() - timedelta(days=1)))
        db.commit()


# ---------------------------------------------------------------- data of a user
def transfer_user_data(from_user_id: str, to_user_id: str, settings: Settings) -> dict:
    """Give everything of one user to another: documents (vectors, files, records),
    conversations and jobs. Used to give the CLI's documents (DEFAULT_USER_ID) to the
    first account. A document the new owner already has is left where it was."""
    registry = DocumentRegistry(settings)
    store = get_store()
    moved, skipped = 0, 0
    for record in registry.list_for_user(from_user_id):
        if registry.find_by_hash(to_user_id, record.sha256):
            skipped += 1
            continue
        store.move_document(record.document_id, from_user_id, to_user_id, to_user_id)
        old_path = Path(record.stored_path)
        new_path = settings.upload_dir / to_user_id / old_path.name
        if old_path.is_file():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(old_path, new_path)
        record.user_id, record.stored_path = to_user_id, str(new_path)
        registry.add(record)
        moved += 1
    with session() as db:
        conversations = db.execute(update(Conversation).where(Conversation.user_id == from_user_id)
                                   .values(user_id=to_user_id)).rowcount
        db.execute(update(Feedback).where(Feedback.user_id == from_user_id).values(user_id=to_user_id))
        db.execute(update(Job).where(Job.user_id == from_user_id, Job.type != "transfer").values(user_id=to_user_id))
        db.commit()
    logger.info("Moved %d document(s) and %d conversation(s) from '%s' to account %s (%d already there)",
                moved, conversations, from_user_id, to_user_id, skipped)
    return {"documents_moved": moved, "documents_skipped": skipped, "conversations_moved": conversations}


def has_data(user_id: str) -> bool:
    with session() as db:
        return bool(db.scalar(select(Document.document_id).where(Document.user_id == user_id).limit(1))
                    or db.scalar(select(Conversation.id).where(Conversation.user_id == user_id).limit(1)))


def delete_account(user_id: str, password: str, settings: Settings) -> None:
    """Delete an account and everything in it. Vectors go first: if Pinecone fails,
    nothing else is deleted, so it can simply be tried again."""
    user = get_user(user_id)
    if user is None:
        return
    if not verify_password(user.password_hash, password):
        raise AuthError("The password is wrong.", "wrong_password", 403)
    get_store().delete_namespace(user_id)
    shutil.rmtree(settings.upload_dir / user_id, ignore_errors=True)
    with session() as db:
        db.execute(delete(Document).where(Document.user_id == user_id))
        for conversation in db.scalars(select(Conversation).where(Conversation.user_id == user_id)):
            db.delete(conversation)  # messages and feedback go with it
        db.execute(delete(Job).where(Job.user_id == user_id))
        db.delete(db.get(User, user_id))  # refresh tokens go with it
        db.commit()
    logger.info("Account %s and all its data were deleted", user_id)
