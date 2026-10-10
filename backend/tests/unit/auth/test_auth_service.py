"""Accounts and sessions: strong passwords, no account enumeration, rotated
refresh tokens with a short grace window, single-use reset codes, and every
password change ending all sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import (
    DuplicateRecordError,
    InactiveAccountError,
    InvalidCredentialsError,
    OtpGenerationError,
    OtpInvalidError,
    TokenInvalidError,
    WeakPasswordError,
)
from app.features.auth import security
from app.features.auth.models import RefreshToken
from app.features.auth.repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.features.auth.service import AuthService

PASSWORD = "Secret123"


@pytest.fixture(autouse=True)
def fast_bcrypt(monkeypatch):
    monkeypatch.setattr(security._AUTH, "bcrypt_rounds", 4)


@pytest.fixture
def auth(session):
    email = AsyncMock()
    svc = AuthService(UserRepository(session), RefreshTokenRepository(session), PasswordResetTokenRepository(session), email)
    return svc, email


def aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@pytest.mark.parametrize("weak", ["Short1A", "NoDigitsHere", "nouppercase1"])
async def test_registration_needs_a_strong_password_and_a_new_email(auth, weak):
    svc, _ = auth
    with pytest.raises(WeakPasswordError):
        await svc.register("a@example.com", weak)
    me, tokens = await svc.register("a@example.com", PASSWORD, full_name="A")
    assert (me.email, me.role, me.full_name) == ("a@example.com", "user", "A") and tokens.access_token and tokens.refresh_token
    with pytest.raises(DuplicateRecordError):
        await svc.register("a@example.com", PASSWORD)


async def test_login_never_reveals_which_part_was_wrong_and_blocks_inactive_accounts(auth):
    svc, _ = auth
    await svc.register("a@example.com", PASSWORD)
    for email, password in (("a@example.com", "Wrong1234"), ("nobody@example.com", PASSWORD)):
        with pytest.raises(InvalidCredentialsError):
            await svc.login(email, password)
    me, tokens = await svc.login("a@example.com", PASSWORD)
    assert security.decode_access_token(tokens.access_token)["sub"] == me.id
    (await svc._users.get_by_email("a@example.com")).is_active = False
    with pytest.raises(InactiveAccountError):
        await svc.login("a@example.com", PASSWORD)


async def test_refresh_rotates_with_a_grace_window_and_logout_revokes_at_once(auth, session):
    svc, _ = auth
    _, first = await svc.register("a@example.com", PASSWORD)
    second = await svc.refresh(first.refresh_token)
    record = await RefreshTokenRepository(session).get_valid_by_raw_token(second.refresh_token)
    assert aware(record.expires_at) - datetime.now(timezone.utc) > timedelta(
        seconds=get_settings().auth.refresh_token_ttl_seconds - 60
    )
    # the client never received `second`: retrying with the old token still works
    assert (await svc.refresh(first.refresh_token)).refresh_token
    old = await RefreshTokenRepository(session).get_valid_by_raw_token(first.refresh_token)
    assert aware(old.expires_at) <= datetime.now(timezone.utc) + timedelta(
        seconds=get_settings().auth.refresh_rotation_grace_seconds + 1
    )
    old.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await session.flush()
    with pytest.raises(TokenInvalidError):
        await svc.refresh(first.refresh_token)

    await svc.logout(second.refresh_token)
    await svc.logout(second.refresh_token)  # already revoked: harmless
    with pytest.raises(TokenInvalidError):
        await svc.refresh(second.refresh_token)


async def test_an_inactive_account_cannot_refresh(auth):
    svc, _ = auth
    _, tokens = await svc.register("a@example.com", PASSWORD)
    (await svc._users.get_by_email("a@example.com")).is_active = False
    with pytest.raises(InactiveAccountError):
        await svc.refresh(tokens.refresh_token)


async def test_password_reset_code_is_emailed_single_use_and_ends_every_session(auth, session):
    svc, email = auth
    _, tokens = await svc.register("a@example.com", PASSWORD)
    await svc.register("b@example.com", PASSWORD)
    assert await svc.request_password_reset("nobody@example.com") is None and not email.send_otp_email.await_count

    otp = await svc.request_password_reset("a@example.com")
    assert len(otp) == get_settings().email.otp_length
    assert email.send_otp_email.await_args.kwargs == {"to_email": "a@example.com", "otp": otp, "purpose": "password_reset"}
    for who, code in (("b@example.com", otp), ("a@example.com", "000000" if otp != "000000" else "111111"),
                      ("nobody@example.com", otp)):
        with pytest.raises(OtpInvalidError):
            await svc.confirm_password_reset(who, code, "NewSecret1")
    with pytest.raises(WeakPasswordError):
        await svc.confirm_password_reset("a@example.com", otp, "weak")

    await svc.confirm_password_reset("a@example.com", otp, "NewSecret1")
    await svc.login("a@example.com", "NewSecret1")
    with pytest.raises(OtpInvalidError):  # single use
        await svc.confirm_password_reset("a@example.com", otp, "Another123")
    with pytest.raises(TokenInvalidError):  # existing sessions ended
        await svc.refresh(tokens.refresh_token)


async def test_otp_generation_gives_up_after_repeated_collisions(auth, monkeypatch):
    svc, _ = auth
    await svc.register("a@example.com", PASSWORD)
    monkeypatch.setattr(svc._reset_tokens, "hash_in_use", AsyncMock(return_value=True))
    with pytest.raises(OtpGenerationError):
        await svc.request_password_reset("a@example.com")


async def test_changing_the_password_needs_the_current_one_and_ends_sessions(auth, session):
    svc, _ = auth
    _, tokens = await svc.register("a@example.com", PASSWORD)
    user = await svc._users.get_by_email("a@example.com")
    with pytest.raises(InvalidCredentialsError):
        await svc.change_password(user, "Wrong1234", "NewSecret1")
    await svc.change_password(user, PASSWORD, "NewSecret1")
    revoked = (await session.execute(select(RefreshToken.revoked))).scalars().all()
    assert revoked and all(revoked)
    await svc.login("a@example.com", "NewSecret1")
