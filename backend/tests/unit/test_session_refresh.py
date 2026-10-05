"""Sessions last until logout: rotated refresh tokens keep a short grace
window (a lost refresh response must not log the user out), new tokens get a
fresh long lifetime, and logout revokes immediately."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.core.exceptions import TokenInvalidError
from app.features.auth.models import RefreshToken
from app.features.auth.repository import PasswordResetTokenRepository, RefreshTokenRepository, UserRepository
from app.features.auth.service import AuthService
from app.shared.models_registry import Base
from db_helpers import add_user, make_session_factory


@pytest.fixture
async def auth():
    engine, factory = await make_session_factory()
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[RefreshToken.__table__]))
    async with factory() as s:
        user = await add_user(s)
        service = AuthService(UserRepository(s), RefreshTokenRepository(s), PasswordResetTokenRepository(s), MagicMock())
        first = await service._issue_token_pair(user)
        await s.commit()
        yield service, s, first
    await engine.dispose()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def test_refresh_issues_a_new_long_lived_token(auth):
    service, s, first = auth
    second = await service.refresh(first.refresh_token)
    assert second.refresh_token != first.refresh_token
    record = await RefreshTokenRepository(s).get_valid_by_raw_token(second.refresh_token)
    remaining = _aware(record.expires_at) - datetime.now(timezone.utc)
    assert remaining > timedelta(seconds=get_settings().auth.refresh_token_ttl_seconds - 60)


async def test_lost_refresh_response_does_not_log_the_user_out(auth):
    """The client never received `second`, so it retries with the old token."""
    service, _, first = auth
    await service.refresh(first.refresh_token)
    retried = await service.refresh(first.refresh_token)
    assert retried.access_token and retried.refresh_token


async def test_rotated_token_stops_working_after_the_grace_window(auth):
    service, s, first = auth
    await service.refresh(first.refresh_token)
    old = (await s.execute(RefreshToken.__table__.select())).first()
    record = await s.get(RefreshToken, old.id)
    assert _aware(record.expires_at) <= datetime.now(timezone.utc) + timedelta(
        seconds=get_settings().auth.refresh_rotation_grace_seconds + 1
    )
    record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await s.flush()
    with pytest.raises(TokenInvalidError):
        await service.refresh(first.refresh_token)


async def test_logout_revokes_immediately(auth):
    service, _, first = auth
    await service.logout(first.refresh_token)
    with pytest.raises(TokenInvalidError):
        await service.refresh(first.refresh_token)
