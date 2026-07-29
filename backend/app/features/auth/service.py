from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog

from app.core.config import get_settings
from app.core.exceptions import (
    DuplicateRecordError,
    InactiveAccountError,
    InvalidCredentialsError,
    TokenInvalidError,
    WeakPasswordError,
)
from app.features.auth.models import PasswordResetToken, RefreshToken, User
from app.features.auth.repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.features.auth.schemas import TokenResponse, UserMeResponse
from app.features.auth.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.features.users.models import UserProfile

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()
_AUTH = _SETTINGS.auth


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _validate_password_strength(password: str) -> None:
    if len(password) < 8:
        raise WeakPasswordError("Must be at least 8 characters long.")
    if not any(c.isdigit() for c in password):
        raise WeakPasswordError("Must contain at least one digit.")
    if not any(c.isupper() for c in password):
        raise WeakPasswordError("Must contain at least one uppercase letter.")


class AuthService:

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        reset_token_repo: PasswordResetTokenRepository,
    ) -> None:
        self._users = user_repo
        self._tokens = token_repo
        self._reset_tokens = reset_token_repo

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = "user",
    ) -> tuple[UserMeResponse, TokenResponse]:
        _validate_password_strength(password)

        if await self._users.email_exists(email):
            raise DuplicateRecordError(
                model="User",
                field="email",
                value=email,
            )

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=False,
        )
        user = await self._users.create(user)

        profile = UserProfile(user_id=user.id)
        self._users.session.add(profile)
        await self._users.session.flush()

        logger.info("user_registered", user_id=str(user.id), role=role)

        tokens = await self._issue_token_pair(user)
        return _to_me_response(user), tokens

    async def login(
        self, email: str, password: str
    ) -> tuple[UserMeResponse, TokenResponse]:
        user = await self._users.get_by_email(email)

        _dummy_hash = "$2b$12$dummy.hash.to.prevent.timing.oracle.attack.padding"
        hashed = user.hashed_password if user else _dummy_hash
        password_ok = verify_password(password, hashed)

        if user is None or not password_ok:
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveAccountError()

        logger.info("user_login", user_id=str(user.id))
        tokens = await self._issue_token_pair(user)
        return _to_me_response(user), tokens

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        old_token = await self._tokens.get_valid_by_raw_token(raw_refresh_token)
        if old_token is None:
            raise TokenInvalidError()

        user = await self._users.get_by_id(old_token.user_id)

        if not user.is_active:
            raise InactiveAccountError()

        old_token.revoked = True
        self._users.session.add(old_token)

        tokens = await self._issue_token_pair(user)
        logger.info("token_refreshed", user_id=str(user.id))
        return tokens

    async def logout(self, raw_refresh_token: str) -> None:
        revoked = await self._tokens.revoke_by_raw_token(raw_refresh_token)
        if not revoked:
            logger.debug("logout_token_not_found_or_already_revoked")

    async def get_me(self, user_id: uuid.UUID) -> UserMeResponse:
        user = await self._users.get_by_id(user_id)
        return _to_me_response(user)

    async def request_password_reset(self, email: str) -> str | None:
        user = await self._users.get_by_email(email)
        if user is None:
            logger.debug("password_reset_email_not_found", email=email)
            return None

        raw_token = secrets.token_urlsafe(48)
        token_hash = _sha256(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
        )
        self._users.session.add(reset_token)
        await self._users.session.flush()

        logger.info("password_reset_token_created", user_id=str(user.id))
        return raw_token

    async def confirm_password_reset(self, raw_token: str, new_password: str) -> None:
        _validate_password_strength(new_password)

        reset_token = await self._reset_tokens.get_valid_by_raw_token(raw_token)
        if reset_token is None:
            raise TokenInvalidError()

        reset_token.used = True
        self._users.session.add(reset_token)

        user = await self._users.get_by_id(reset_token.user_id)
        user.hashed_password = hash_password(new_password)
        self._users.session.add(user)

        await self._tokens.revoke_all_for_user(user.id)

        await self._users.session.flush()
        logger.info("password_reset_applied", user_id=str(user.id))

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password or ""):
            raise InvalidCredentialsError()

        _validate_password_strength(new_password)
        user.hashed_password = hash_password(new_password)
        self._users.session.add(user)

        await self._tokens.revoke_all_for_user(user.id)
        await self._users.session.flush()
        logger.info("password_changed", user_id=str(user.id))

    async def _issue_token_pair(self, user: User) -> TokenResponse:
        access_token, expires_in = create_access_token(user.id, user.role)
        raw_refresh, refresh_hash, refresh_expires = create_refresh_token()

        refresh_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=refresh_expires,
            revoked=False,
        )
        self._users.session.add(refresh_record)
        await self._users.session.flush()

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )


def _to_me_response(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )
