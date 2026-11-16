"""Accounts: register, log in, stay logged in, log out, and manage your account.

  access token   returned in the body; send it as "Authorization: Bearer <token>" with every request.
                 It works for ACCESS_TOKEN_MINUTES; then call /auth/refresh.
  refresh token  set as an HttpOnly cookie (scripts can't read it) limited to /api/v1/auth;
                 /auth/refresh swaps it for a new one and returns a new access token.
"""

import asyncio

from fastapi import APIRouter, Cookie, Depends, Request, Response

from accounts import service
from accounts.security import create_access_token
from api.dependencies import JobQueue, current_user, get_queue
from api.errors import APIError
from api.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserOut,
)
from api.services.rate_limit import RateLimiter
from database.models import User
from utils.config import get_settings
from utils.exceptions import AuthError
from utils.logger import get_logger
from utils.request_context import current_request_id
from workers import jobs, queue

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "rag_refresh"
_COOKIE_PATH = "/api/v1/auth"
_MINUTE = 60
# Attempts allowed per window
_LOGIN_PER_IP = (20, 15 * _MINUTE)
_FAILED_LOGINS_PER_EMAIL = (5, 15 * _MINUTE)
_REGISTRATIONS_PER_IP = (5, 60 * _MINUTE)


def _client(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE, token, max_age=settings.refresh_token_days * 24 * 3600, path=_COOKIE_PATH,
        httponly=True, secure=settings.auth_cookie_secure,
        samesite="strict",  # never sent with requests started by other websites
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)


async def _log_in(response: Response, request: Request, user: User, family_id: str | None = None,
                  refresh_token: str | None = None) -> TokenResponse:
    """Access token in the body, refresh token in the cookie."""
    settings = get_settings()
    if refresh_token is None:
        user_agent, ip = _client(request)
        refresh_token = await asyncio.to_thread(service.issue_refresh_token, user.id, settings, family_id,
                                                user_agent, ip)
    _set_refresh_cookie(response, refresh_token)
    access_token, expires_in = create_access_token(user, settings)
    return TokenResponse(access_token=access_token, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=201, summary="Create an account (and log in)")
async def register(body: RegisterRequest, request: Request, response: Response,
                   job_queue: JobQueue = Depends(get_queue)) -> TokenResponse:
    limiter = RateLimiter(job_queue)
    await limiter.hit(f"register:ip:{_client(request)[1]}", *_REGISTRATIONS_PER_IP)
    settings = get_settings()
    first_account = await asyncio.to_thread(service.count_users) == 0
    user = await asyncio.to_thread(service.register, body.email, body.password, body.name, settings)
    tokens = await _log_in(response, request, user)

    # The first account receives the documents and chats made so far without accounts
    if first_account and await asyncio.to_thread(service.has_data, settings.default_user_id):
        job = jobs.create_job("transfer", user.id, request_id=current_request_id(),
                              params={"from_user": settings.default_user_id})
        try:
            await job_queue.enqueue(queue.TRANSFER, job.id, job_id=job.id)
            tokens.transfer_job_id = job.id
        except APIError as exc:
            jobs.fail_job(job.id, exc.message)
            logger.warning("Could not start moving '%s' data to the first account; run: "
                           "python main.py move-data --from %s --to <email>",
                           settings.default_user_id, settings.default_user_id)
    return tokens


@router.post("/login", response_model=TokenResponse, summary="Log in")
async def login(body: LoginRequest, request: Request, response: Response,
                job_queue: JobQueue = Depends(get_queue)) -> TokenResponse:
    limiter = RateLimiter(job_queue)
    email = service.normalize_email(body.email)
    await limiter.hit(f"login:ip:{_client(request)[1]}", *_LOGIN_PER_IP)
    email_key = f"login:email:{email}"
    await limiter.check(email_key, _FAILED_LOGINS_PER_EMAIL[0])
    try:
        user = await asyncio.to_thread(service.authenticate, email, body.password)
    except AuthError as exc:
        if exc.code == "invalid_credentials":
            await limiter.hit(email_key, *_FAILED_LOGINS_PER_EMAIL)
        raise
    await limiter.reset(email_key)
    return await _log_in(response, request, user)


@router.post("/refresh", response_model=TokenResponse, summary="Get a new access token (uses the login cookie)")
async def refresh(request: Request, response: Response,
                  refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE)) -> TokenResponse:
    if not refresh_token:
        raise APIError(401, "session_expired", "Your session ended. Please log in again.")
    user_agent, ip = _client(request)
    try:
        user, new_token = await asyncio.to_thread(service.rotate_refresh_token, refresh_token, get_settings(),
                                                  user_agent, ip)
    except AuthError:
        # The cookie is useless now; remove it so the browser stops sending it
        failed = Response()
        _clear_refresh_cookie(failed)
        raise APIError(401, "session_expired", "Your session ended. Please log in again.",
                       headers={"set-cookie": failed.headers["set-cookie"]})
    return await _log_in(response, request, user, refresh_token=new_token)


@router.post("/logout", status_code=204, summary="Log out this device")
async def logout(refresh_token: str | None = Cookie(None, alias=REFRESH_COOKIE)) -> Response:
    if refresh_token:
        await asyncio.to_thread(service.revoke_refresh_token, refresh_token)
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserOut, summary="Who is logged in")
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut, summary="Change your name")
def update_me(body: UpdateMeRequest, user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(service.update_name(user.id, body.name))


@router.post("/change-password", response_model=TokenResponse,
             summary="Change your password (logs out your other devices)")
async def change_password(body: ChangePasswordRequest, request: Request, response: Response,
                          user: User = Depends(current_user)) -> TokenResponse:
    user = await asyncio.to_thread(service.change_password, user.id, body.current_password, body.new_password)
    return await _log_in(response, request, user)  # this device stays logged in


@router.delete("/me", status_code=204, summary="Delete your account and all your documents and chats")
async def delete_me(body: DeleteAccountRequest, user: User = Depends(current_user)) -> Response:
    await asyncio.to_thread(service.delete_account, user.id, body.password, get_settings())
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response
