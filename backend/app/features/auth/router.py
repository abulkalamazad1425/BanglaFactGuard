from __future__ import annotations

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

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_auth_service(
    session: AsyncSession = Depends(get_async_session),
) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        token_repo=RefreshTokenRepository(session),
        reset_token_repo=PasswordResetTokenRepository(session),
    )


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
    user_data, tokens = await svc.register(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )

    return user_data.model_copy(
        update={
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "token_type": tokens.token_type,
            "expires_in": tokens.expires_in,
        }
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
    await svc.logout(raw_refresh_token=body.refresh_token)


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    from app.features.auth.service import _to_me_response

    return _to_me_response(current_user)


@router.post(
    "/password-reset/request",
    status_code=status.HTTP_200_OK,
    summary="Request a password-reset OTP by email",
)
async def request_password_reset(
    body: PasswordResetRequest,
    svc: AuthService = Depends(_get_auth_service),
) -> dict:
    await svc.request_password_reset(email=body.email)
    return {"message": "If the email is registered, a verification code has been sent."}


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_200_OK,
    summary="Confirm password reset with the emailed OTP",
)
async def confirm_password_reset(
    body: PasswordResetConfirm,
    svc: AuthService = Depends(_get_auth_service),
) -> dict:
    await svc.confirm_password_reset(
        email=body.email,
        otp=body.otp,
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
    await svc.change_password(
        user=current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    return {"message": "Password changed successfully. Please log in again."}
