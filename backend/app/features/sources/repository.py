from __future__ import annotations

import logging

from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.sources.models import VerifiedSource
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SourceRepository(BaseRepository[VerifiedSource]):

    model_class = VerifiedSource

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_canonical_name(self, canonical_name: str) -> VerifiedSource | None:
        stmt = (
            select(VerifiedSource)
            .where(VerifiedSource.canonical_name == canonical_name.lower().strip())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_alias(self, alias: str) -> VerifiedSource | None:
        alias_json = cast([alias], JSONB)
        stmt = (
            select(VerifiedSource)
            .where(
                and_(
                    VerifiedSource.aliases.op("@>")(alias_json),
                    VerifiedSource.is_active.is_(True),
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_source(self, raw_name: str) -> VerifiedSource | None:
        normalised = raw_name.strip().lower()

        source = await self.get_by_canonical_name(normalised)
        if source:
            logger.debug("Source resolved via canonical_name", extra={"raw": raw_name})
            return source

        source = await self.get_by_alias(raw_name.strip())
        if source:
            logger.debug("Source resolved via alias", extra={"raw": raw_name})
            return source

        logger.debug("Source not resolved in DB", extra={"raw": raw_name})
        return None

    async def list_active(
        self,
        *,
        language: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerifiedSource]:
        stmt = select(VerifiedSource).where(VerifiedSource.is_active.is_(True))
        if language:
            stmt = stmt.where(VerifiedSource.language == language.lower())
        stmt = (
            stmt.order_by(VerifiedSource.canonical_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(VerifiedSource)
            .where(VerifiedSource.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_all(
        self,
        *,
        language: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[VerifiedSource]:
        stmt = select(VerifiedSource)
        if language:
            stmt = stmt.where(VerifiedSource.language == language.lower())
        stmt = (
            stmt.order_by(VerifiedSource.canonical_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        query: str,
        *,
        include_inactive: bool,
        language: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[VerifiedSource], int]:
        """Sources matching `query` in the Bangla or English name, domain,
        base URL or aliases (best matches first), with the matching total."""
        from sqlalchemy import String, func

        from app.shared.utils.keyword_search import KeywordSearch

        search = KeywordSearch(
            query,
            [
                VerifiedSource.display_name,
                VerifiedSource.display_name_en,
                VerifiedSource.canonical_name,
                VerifiedSource.base_url,
                cast(VerifiedSource.aliases, String),
            ],
            headline_column=VerifiedSource.display_name,
        )
        conditions = []
        if not include_inactive:
            conditions.append(VerifiedSource.is_active.is_(True))
        if language:
            conditions.append(VerifiedSource.language == language.lower())
        if search.active:
            conditions.append(search.condition)
        stmt = (
            select(VerifiedSource)
            .where(*conditions)
            .order_by(*search.order_by(), VerifiedSource.canonical_name.asc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.session.execute(stmt)).scalars().all())
        total = (
            await self.session.execute(select(func.count()).select_from(VerifiedSource).where(*conditions))
        ).scalar_one()
        return items, total

    async def count_all(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(VerifiedSource)
        result = await self.session.execute(stmt)
        return result.scalar_one()
