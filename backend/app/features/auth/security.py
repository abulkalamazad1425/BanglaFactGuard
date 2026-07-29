
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





def hash_password(plain: str) -> str:

    plain_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=_AUTH.bcrypt_rounds)
    hashed = bcrypt.hashpw(plain_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    plain_bytes = plain.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(plain_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False







def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, int]:
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
    raw = secrets.token_urlsafe(64)
    token_hash = _sha256(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=_AUTH.refresh_token_ttl_seconds
    )
    return raw, token_hash, expires_at


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()







def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _AUTH.secret_key, algorithms=[_AUTH.algorithm])
        if payload.get("type") != "access":
            raise TokenInvalidError()
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise TokenInvalidError()






_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    if credentials is None:
        raise TokenInvalidError()

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise TokenInvalidError()


    async with AsyncSessionLocal() as session:
        user: User | None = await session.get(User, user_id)

    if user is None:
        raise TokenInvalidError()

    if not user.is_active:
        raise InactiveAccountError()

    return user


def require_role(*roles: str):

    async def _check_role(
        user: User = Depends(get_current_user),
    ) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(required_role=" | ".join(roles))
        return user

    return _check_role


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> "User | None":
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
        async with AsyncSessionLocal() as session:
            user: User | None = await session.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user
    except Exception:
        return None
