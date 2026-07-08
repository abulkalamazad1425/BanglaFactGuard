"""
app/features/auth/security.py
==============================
JWT issuance/decoding and bcrypt password hashing utilities.

Also provides FastAPI dependency functions:
    get_current_user   — extracts & validates Bearer JWT, returns User ORM instance
    require_role       — functional dependency factory for RBAC enforcement

Design decisions:
- python-jose is used for JWT encoding/decoding (HS256 default).
- passlib[bcrypt] is used for password hashing with a configurable work factor.
- The dependency `get_current_user` is a pure FastAPI Depends function: it reads
  the Authorization header, decodes the token, loads the User from DB, and
  raises domain exceptions on failure. No business logic lives here.
- `require_role(*roles)` returns a dependency that calls `get_current_user`
  and then checks the role, raising PermissionDeniedError if it does not match.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    InactiveAccountError,
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.db.engine import AsyncSessionLocal
from app.features.auth.models import User

_SETTINGS = get_settings()
_AUTH = _SETTINGS.auth

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* using the configured work factor."""
    # Truncate to 72 bytes to match passlib's historical behavior and avoid ValueError
    plain_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=_AUTH.bcrypt_rounds)
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* value."""
    plain_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(plain_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# JWT token creation
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
    """
    Issue a signed JWT access token.

    Returns:
        (encoded_token, expires_in_seconds) tuple.
    """
    now = datetime.now(timezone.utc)
    ttl = _AUTH.access_token_ttl_seconds
    expire = now + timedelta(seconds=ttl)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, _AUTH.secret_key, algorithm=_AUTH.algorithm)
    return token, ttl


def create_refresh_token() -> tuple[str, str, datetime]:
    """
    Generate a cryptographically random refresh token.

    Returns:
        (raw_token, sha256_hash, expires_at) where *raw_token* is sent to the
        client and only *sha256_hash* is stored in the database.
    """
    raw = secrets.token_urlsafe(64)
    token_hash = _sha256(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=_AUTH.refresh_token_ttl_seconds
    )
    return raw, token_hash, expires_at


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ---------------------------------------------------------------------------
# JWT decoding
# ---------------------------------------------------------------------------


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Returns:
        The decoded payload dict.

    Raises:
        TokenExpiredError: If the token has expired.
        TokenInvalidError: If the token signature or format is invalid.
    """
    try:
        payload = jwt.decode(token, _AUTH.secret_key, algorithms=[_AUTH.algorithm])
        if payload.get("type") != "access":
            raise TokenInvalidError()
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    """
    FastAPI dependency: extract and validate the Bearer JWT, then load the User.

    Usage::

        @router.get("/me")
        async def me(user: User = Depends(get_current_user)):
            ...

    Raises:
        TokenInvalidError: If no token is provided or the token is malformed.
        TokenExpiredError: If the token has expired.
        InactiveAccountError: If the user's account is deactivated.
    """
    if credentials is None:
        raise TokenInvalidError()

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise TokenInvalidError()

    # Load user from DB with a fresh session scoped to this dependency call.
    async with AsyncSessionLocal() as session:
        user: User | None = await session.get(User, user_id)

    if user is None:
        raise TokenInvalidError()

    if not user.is_active:
        raise InactiveAccountError()

    return user


def require_role(*roles: str):
    """
    Functional dependency factory for role-based access control.

    Usage::

        @router.post("/admin/experts")
        async def create_expert(
            user: User = Depends(require_role("admin")),
        ):
            ...

    Returns a FastAPI dependency function that calls `get_current_user` and
    then validates the role.
    """

    async def _check_role(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(required_role=" | ".join(roles))
        return user

    return _check_role
