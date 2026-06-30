"""
app/features/auth/schemas.py
==============================
Pydantic schemas for the authentication feature.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for POST /api/v1/auth/register."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT access + refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token TTL in seconds")


class RefreshRequest(BaseModel):
    """Request body for POST /api/v1/auth/refresh and /logout."""
    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Request body for POST /api/v1/auth/password-reset/request."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Request body for POST /api/v1/auth/password-reset/confirm."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """Request body for POST /api/v1/auth/change-password."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserMeResponse(BaseModel):
    """Response for GET /api/v1/auth/me and POST /api/v1/auth/register."""
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    # Token fields are optional — only included on register/login responses
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    expires_in: int | None = None

    model_config = {"from_attributes": True}
