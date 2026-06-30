"""
app/features/auth/router.py
==============================
Authentication API endpoints.

POST /api/v1/auth/register           — Create a new user account
POST /api/v1/auth/login              — Authenticate and receive JWT pair
POST /api/v1/auth/refresh            — Rotate refresh token
POST /api/v1/auth/logout             — Revoke refresh token
GET  /api/v1/auth/me                 — Get current user profile
POST /api/v1/auth/password-reset/request  — Send reset email
POST /api/v1/auth/password-reset/confirm  — Apply new password with token
POST /api/v1/auth/change-password    — Authenticated password change
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.features.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserMeResponse,
)
from app.features.auth.security import get_current_user
from app.features.auth.service import AuthService
from app.shared.dependencies import get_async_session

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------


def _get_auth_service(session: AsyncSession = Depends(get_async_session)) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        token_repo=RefreshTokenRepository(session),
        reset_token_repo=PasswordResetTokenRepository(session),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UserMeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: RegisterRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> UserMeResponse:
    """
    Create a new user account with email/password.
    The new account receives the 'user' role and is automatically logged in
    (access + refresh tokens are returned in the response).
    """
    user_data, tokens = await svc.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    # Attach tokens to user response via extra fields
    return UserMeResponse(
        **user_data.model_dump(),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT pair",
)
async def login(
    body: LoginRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """Authenticate with email and password. Returns access + refresh tokens."""
    _, tokens = await svc.login(email=body.email, password=body.password)
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token",
)
async def refresh_token(
    body: RefreshRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> TokenResponse:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is revoked immediately.
    """
    return await svc.refresh(raw_refresh_token=body.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke refresh token and log out",
)
async def logout(
    body: RefreshRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> None:
    """Revoke the supplied refresh token. Idempotent."""
    await svc.logout(raw_refresh_token=body.refresh_token)


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    """Return the authenticated user's profile information."""
    from app.features.auth.service import _to_me_response
    return _to_me_response(current_user)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_200_OK,
    summary="Request a password reset email",
)
async def request_password_reset(
    body: PasswordResetRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> dict:
    """
    Send a password reset link to the given email address.
    Always returns 200 regardless of whether the email exists (prevents enumeration).
    In development, the raw token is logged.
    """
    raw_token = await svc.request_password_reset(email=body.email)
    if raw_token:
        # In production: send via NotificationService/email
        # In development: log it so developers can test
        logger.info("password_reset_token_issued", token=raw_token[:8] + "…")
    return {"message": "If the email is registered, a reset link has been sent."}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset with token",
)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    svc: AuthService = Depends(_get_auth_service),
) -> dict:
    """Apply a new password using a valid password-reset token."""
    await svc.confirm_password_reset(
        raw_token=body.token,
        new_password=body.new_password,
    )
    return {"message": "Password has been reset successfully."}


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password (authenticated)",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    svc: AuthService = Depends(_get_auth_service),
) -> dict:
    """
    Change the authenticated user's own password.
    Requires the current password for verification.
    Revokes all existing refresh tokens on success.
    """
    await svc.change_password(
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"message": "Password changed successfully. Please log in again."}
