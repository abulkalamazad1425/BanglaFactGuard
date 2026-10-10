"""Token lookups only ever return a live token; role listings for admin pages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.features.auth.models import PasswordResetToken, RefreshToken
from app.features.auth.repository import (
    PasswordResetTokenRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.shared.utils.hashing import sha256_hex
from tests.helpers.db import add_user

LATER = datetime.now(timezone.utc) + timedelta(hours=1)
EARLIER = datetime.now(timezone.utc) - timedelta(hours=1)


async def test_only_unrevoked_unexpired_tokens_are_valid(session):
    user = await add_user(session)
    session.add_all([
        RefreshToken(user_id=user.id, token_hash=sha256_hex("live"), expires_at=LATER),
        RefreshToken(user_id=user.id, token_hash=sha256_hex("old"), expires_at=EARLIER),
        RefreshToken(user_id=user.id, token_hash=sha256_hex("revoked"), expires_at=LATER, revoked=True),
        PasswordResetToken(user_id=user.id, token_hash=sha256_hex("123456"), expires_at=LATER),
        PasswordResetToken(user_id=user.id, token_hash=sha256_hex("654321"), expires_at=LATER, used=True),
    ])
    await session.flush()
    tokens, resets = RefreshTokenRepository(session), PasswordResetTokenRepository(session)
    assert await tokens.get_valid_by_raw_token("live")
    assert not await tokens.get_valid_by_raw_token("old") and not await tokens.get_valid_by_raw_token("revoked")
    assert await resets.get_valid_by_raw_token("123456") and not await resets.get_valid_by_raw_token("654321")
    assert await resets.hash_in_use(sha256_hex("654321")) and not await resets.hash_in_use(sha256_hex("000000"))

    assert await tokens.revoke_by_raw_token("live") and not await tokens.revoke_by_raw_token("live")
    assert await tokens.delete_expired() == 1
    session.add(RefreshToken(user_id=user.id, token_hash=sha256_hex("second"), expires_at=LATER))
    await session.flush()
    assert await tokens.revoke_all_for_user(user.id) == 1


async def test_users_by_email_and_role(session):
    users = UserRepository(session)
    expert = await add_user(session, role="expert", total_submissions=0)
    await add_user(session)
    assert (await users.get_by_email(expert.email)).id == expert.id and await users.email_exists(expert.email)
    assert [u.id for u in await users.list_by_role("expert")] == [expert.id] and await users.count_by_role("expert") == 1
    await users.increment_submission_count(expert.id)
    await session.refresh(expert)
    assert expert.total_submissions == 1
