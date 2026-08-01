from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=4, max_length=10, description="OTP emailed to the user")
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserMeResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool

    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None

    model_config = {"from_attributes": True}
