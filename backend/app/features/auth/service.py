"""
app/features/auth/service.py
==============================
Authentication service: registration, login, JWT lifecycle, password reset.

Responsibilities:
    register()                — create user + profile, return token pair
    login()                   — verify credentials, issue JWT pair
    refresh()                 — rotate refresh token
    logout()                  — revoke refresh token
    get_me()                  — return current user data
    request_password_reset()  — generate and (optionally) email a reset token
    confirm_password_reset()  — validate token and apply new password
    change_password()         — authenticated password change (requires current pw)

Design decisions:
- Passwords are validated for strength before hashing.
- Generic error messages are used for login failure to prevent account enumeration.
- Refresh tokens use the rotation pattern: old token is revoked and a new one issued.
- All DB mutations flush but do NOT commit — the session dependency handles that.
"""

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
    """
    Raise WeakPasswordError if the password does not meet requirements:
        - Minimum 8 characters
        - At least one digit
        - At least one uppercase letter
    """
    if len(password) < 8:
        raise WeakPasswordError("Must be at least 8 characters long.")
    if not any(c.isdigit() for c in password):
        raise WeakPasswordError("Must contain at least one digit.")
    if not any(c.isupper() for c in password):
        raise WeakPasswordError("Must contain at least one uppercase letter.")


class AuthService:
    """
    Handles user registration, authentication, and JWT lifecycle.

    All repository instances are injected, making this class fully testable.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        reset_token_repo: PasswordResetTokenRepository,
    ) -> None:
        self._users = user_repo
        self._tokens = token_repo
        self._reset_tokens = reset_token_repo

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    async def register(
        self,
        email: str,
        password: str,
        full_name: str | None = None,
        role: str = "user",
    ) -> tuple[UserMeResponse, TokenResponse]:
        """
        Register a new account and return the user data + a JWT token pair.

        Args:
            email:     User's email address (must be unique).
            password:  Plain-text password (validated for strength).
            full_name: Optional display name.
            role:      Role assigned at creation ('user' by default).

        Returns:
            (UserMeResponse, TokenResponse) — user data and JWT pair.

        Raises:
            WeakPasswordError:     If the password fails strength validation.
            DuplicateRecordError:  If the email is already registered.
        """
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

        # Create default profile
        profile = UserProfile(user_id=user.id)
        self._users.session.add(profile)
        await self._users.session.flush()

        logger.info("user_registered", user_id=str(user.id), role=role)

        tokens = await self._issue_token_pair(user)
        return _to_me_response(user), tokens

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def login(self, email: str, password: str) -> tuple[UserMeResponse, TokenResponse]:
        """
        Authenticate with email + password, return a JWT pair.

        Generic error is raised on failure (no indication of which field failed).
        """
        user = await self._users.get_by_email(email)

        # Timing-safe: always verify even if user is None (use a dummy hash)
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

    # ------------------------------------------------------------------
    # Token Refresh
    # ------------------------------------------------------------------

    async def refresh(self, raw_refresh_token: str) -> TokenResponse:
        """
        Rotate a refresh token: revoke the old one, issue a new pair.

        Raises:
            TokenInvalidError: If the token is not found, revoked, or expired.
        """
        old_token = await self._tokens.get_valid_by_raw_token(raw_refresh_token)
        if old_token is None:
            raise TokenInvalidError()

        user = await self._users.get_by_id(old_token.user_id)

        if not user.is_active:
            raise InactiveAccountError()

        # Revoke old token
        old_token.revoked = True
        self._users.session.add(old_token)

        tokens = await self._issue_token_pair(user)
        logger.info("token_refreshed", user_id=str(user.id))
        return tokens

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    async def logout(self, raw_refresh_token: str) -> None:
        """Revoke a refresh token. Idempotent — no error if already revoked."""
        revoked = await self._tokens.revoke_by_raw_token(raw_refresh_token)
        if not revoked:
            logger.debug("logout_token_not_found_or_already_revoked")

    # ------------------------------------------------------------------
    # Current User
    # ------------------------------------------------------------------

    async def get_me(self, user_id: uuid.UUID) -> UserMeResponse:
        """Return profile data for the authenticated user."""
        user = await self._users.get_by_id(user_id)
        return _to_me_response(user)

    # ------------------------------------------------------------------
    # Password Reset
    # ------------------------------------------------------------------

    async def request_password_reset(self, email: str) -> str | None:
        """
        Generate a password-reset token for the user with the given email.

        Returns the raw token string so the caller can send it via email.
        Returns None if the email is not found (caller should NOT reveal this
        to the HTTP client — always respond 200 to prevent email enumeration).
        """
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
        """
        Apply a new password using a valid reset token.

        Raises:
            TokenInvalidError:  Token not found, expired, or already used.
            WeakPasswordError:  New password fails strength validation.
        """
        _validate_password_strength(new_password)

        reset_token = await self._reset_tokens.get_valid_by_raw_token(raw_token)
        if reset_token is None:
            raise TokenInvalidError()

        reset_token.used = True
        self._users.session.add(reset_token)

        user = await self._users.get_by_id(reset_token.user_id)
        user.hashed_password = hash_password(new_password)
        self._users.session.add(user)

        # Invalidate all existing refresh tokens for security
        await self._tokens.revoke_all_for_user(user.id)

        await self._users.session.flush()
        logger.info("password_reset_applied", user_id=str(user.id))

    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        """
        Allow an authenticated user to change their own password.

        Raises:
            InvalidCredentialsError: Current password is wrong.
            WeakPasswordError:       New password fails strength validation.
        """
        if not verify_password(current_password, user.hashed_password or ""):
            raise InvalidCredentialsError()

        _validate_password_strength(new_password)
        user.hashed_password = hash_password(new_password)
        self._users.session.add(user)

        await self._tokens.revoke_all_for_user(user.id)
        await self._users.session.flush()
        logger.info("password_changed", user_id=str(user.id))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _issue_token_pair(self, user: User) -> TokenResponse:
        """Create and persist a new access + refresh token pair."""
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


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _to_me_response(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        is_verified=user.is_verified,
    )
