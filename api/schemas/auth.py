from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from accounts.service import MAX_PASSWORD_CHARS


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=MAX_PASSWORD_CHARS, description="8 to 128 characters")
    name: str = Field("", max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=MAX_PASSWORD_CHARS)


class UpdateMeRequest(BaseModel):
    name: str = Field(max_length=100)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_CHARS)
    new_password: str = Field(max_length=MAX_PASSWORD_CHARS)


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD_CHARS, description="Your password, to confirm")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: Literal["user", "admin"]
    created_at: datetime
    last_login_at: datetime | None


class TokenResponse(BaseModel):
    """The refresh token is not in here: it is set as an HttpOnly cookie that page
    scripts can't read, and is sent automatically to /api/v1/auth/refresh."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds; refresh a little before this
    user: UserOut
    transfer_job_id: str | None = None  # first account only: the job moving the CLI's documents to it
