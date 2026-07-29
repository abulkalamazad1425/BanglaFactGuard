
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.features.auth.models import PasswordResetToken, RefreshToken, User
from app.shared.base_repository import BaseRepository


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class UserRepository(BaseRepository[User]):

    model_class = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return await self.get_by_email(email) is not None

    async def get_active_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email, User.is_active.is_(True))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_role(
        self, role: str, *, limit: int = 50, offset: int = 0
    ) -> list[User]:
        stmt = (
            select(User)
            .where(User.role == role)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_role(self, role: str) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(User).where(User.role == role)
        result = await self.session.execute(stmt)
        return result.scalar_one()


class RefreshTokenRepository(BaseRepository[RefreshToken]):

    model_class = RefreshToken

    async def get_valid_by_raw_token(self, raw_token: str) -> RefreshToken | None:
        token_hash = _sha256(raw_token)
        now = datetime.now(timezone.utc)
        stmt = (
            select(RefreshToken)
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > now,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_by_raw_token(self, raw_token: str) -> bool:
        token_hash = _sha256(raw_token)
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
        ).limit(1)
        result = await self.session.execute(stmt)
        token = result.scalar_one_or_none()
        if token is None:
            return False
        token.revoked = True
        self.session.add(token)
        await self.session.flush()
        return True

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked.is_(False),
        )
        result = await self.session.execute(stmt)
        tokens = list(result.scalars().all())
        for token in tokens:
            token.revoked = True
        self.session.add_all(tokens)
        await self.session.flush()
        return len(tokens)

    async def delete_expired(self) -> int:
        from sqlalchemy import delete as sa_delete
        now = datetime.now(timezone.utc)
        stmt = sa_delete(RefreshToken).where(RefreshToken.expires_at < now)
        result = await self.session.execute(stmt)
        return result.rowcount


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):

    model_class = PasswordResetToken

    async def get_valid_by_raw_token(self, raw_token: str) -> PasswordResetToken | None:
        token_hash = _sha256(raw_token)
        now = datetime.now(timezone.utc)
        stmt = (
            select(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used.is_(False),
                PasswordResetToken.expires_at > now,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
