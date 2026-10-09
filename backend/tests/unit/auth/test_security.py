"""Password hashing, access tokens and the request-user dependencies."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core.exceptions import (
    InactiveAccountError,
    PermissionDeniedError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.features.auth import security
from tests.helpers.db import add_user


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    monkeypatch.setattr(security._AUTH, "bcrypt_rounds", 4)


def bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def token(**claims) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(uuid.uuid4()), "role": "user", "type": "access", "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(claims)
    return jwt.encode(payload, security._AUTH.secret_key, algorithm=security._AUTH.algorithm)


def test_passwords_are_salted_hashes_compared_on_the_first_72_bytes():
    hashed = security.hash_password("Secret123")
    assert hashed != security.hash_password("Secret123") and security.verify_password("Secret123", hashed)
    assert not security.verify_password("Secret124", hashed)
    assert security.verify_password("x" * 80, security.hash_password("x" * 72 + "ignored"))
    assert not security.verify_password("Secret123", "not-a-bcrypt-hash")


def test_access_tokens_round_trip_and_reject_expired_tampered_or_refresh_tokens():
    uid = uuid.uuid4()
    access, ttl = security.create_access_token(uid, "expert")
    assert security.decode_access_token(access)["sub"] == str(uid) and ttl == security._AUTH.access_token_ttl_seconds
    with pytest.raises(TokenExpiredError):
        security.decode_access_token(token(exp=datetime.now(timezone.utc) - timedelta(seconds=1)))
    for bad in (token(type="refresh"), access + "x", "garbage"):
        with pytest.raises(TokenInvalidError):
            security.decode_access_token(bad)
    raw, digest, expires = security.create_refresh_token()
    assert len(raw) > 64 and digest != raw and expires > datetime.now(timezone.utc)


@pytest.fixture
def users_db(db, monkeypatch):
    monkeypatch.setattr(security, "AsyncSessionLocal", db)
    return db


async def test_the_request_user_must_exist_and_be_active(users_db):
    async with users_db() as s:
        active, inactive = await add_user(s, role="expert"), await add_user(s, is_active=False)
        await s.commit()
    assert (await security.get_current_user(bearer(token(sub=str(active.id))))).id == active.id
    with pytest.raises(InactiveAccountError):
        await security.get_current_user(bearer(token(sub=str(inactive.id))))
    for creds in (None, bearer(token()), bearer(token(sub="not-a-uuid"))):
        with pytest.raises(TokenInvalidError):
            await security.get_current_user(creds)

    assert (await security.get_current_user_optional(bearer(token(sub=str(active.id))))).id == active.id
    for creds in (None, bearer("garbage"), bearer(token(sub=str(inactive.id))), bearer(token())):
        assert await security.get_current_user_optional(creds) is None

    check = security.require_role("admin", "expert")
    assert await check(active) is active
    with pytest.raises(PermissionDeniedError):
        await security.require_role("admin")(active)
