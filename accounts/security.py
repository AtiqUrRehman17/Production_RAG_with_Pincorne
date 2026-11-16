"""Passwords and login tokens.

  password       stored only as an Argon2 hash (slow on purpose, so stolen hashes are hard to crack)
  access token   a signed JWT the frontend sends with every request (Authorization: Bearer ...);
                 short-lived (ACCESS_TOKEN_MINUTES), checked without a database lookup of the token
  refresh token  a long random value kept in a cookie, used only to get a new access token;
                 the database keeps just its SHA-256 hash, so a database leak reveals no logins
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from database.models import User
from utils.config import Settings
from utils.exceptions import AuthError, ConfigurationError

_hasher = PasswordHasher()
# Checked when the email is unknown, so a wrong email takes as long as a wrong password
_DUMMY_HASH = _hasher.hash("not-a-real-password")
_ALGORITHM = "HS256"
_MIN_SECRET_CHARS = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when the hash was made with older (weaker) settings."""
    return _hasher.check_needs_rehash(password_hash)


def _secret(settings: Settings) -> str:
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    if len(secret) < _MIN_SECRET_CHARS:
        raise ConfigurationError(f"JWT_SECRET must be set in .env (at least {_MIN_SECRET_CHARS} characters).")
    return secret


def check_secret(settings: Settings) -> None:
    _secret(settings)


def _password_version(user: User) -> int:
    return int(user.password_changed_at.timestamp())


def create_access_token(user: User, settings: Settings) -> tuple[str, int]:
    """A signed token and the seconds it stays valid."""
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    claims = {"sub": user.id, "role": user.role, "type": "access", "pwd": _password_version(user),
              "iat": now, "exp": now + lifetime, "jti": secrets.token_hex(8)}  # jti: every token unique
    return jwt.encode(claims, _secret(settings), algorithm=_ALGORITHM), int(lifetime.total_seconds())


def read_access_token(token: str, settings: Settings) -> dict:
    """The token's claims. Raises AuthError: token_expired (get a new one with /auth/refresh)
    or invalid_token (log in again)."""
    try:
        claims = jwt.decode(token, _secret(settings), algorithms=[_ALGORITHM],
                            options={"require": ["sub", "exp", "iat", "type", "pwd"]})
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Your session expired. Refresh it or log in again.", "token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Your login is not valid. Please log in again.", "invalid_token") from exc
    if claims["type"] != "access":
        raise AuthError("Your login is not valid. Please log in again.", "invalid_token")
    return claims


def token_matches_password(claims: dict, user: User) -> bool:
    """False for tokens made before the password was changed."""
    return claims["pwd"] == _password_version(user)


def new_refresh_token() -> tuple[str, str]:
    """A new refresh token and the hash that is stored."""
    token = secrets.token_urlsafe(48)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
