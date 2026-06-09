"""
app/features/sources/repository.py
=====================================
Repository for the sources feature.

Migrated from: app/repositories/source_repository.py
"""

from __future__ import annotations

import logging

from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.sources.models import SourceRegistry
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SourceRepository(BaseRepository[SourceRegistry]):
    """
    Async repository for SourceRegistry ORM model.

    Provides source resolution, alias lookup, and active-source listing.
    """

    model_class = SourceRegistry

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_canonical_name(self, canonical_name: str) -> SourceRegistry | None:
        """Fetch a source by its canonical domain name."""
        stmt = (
            select(SourceRegistry)
            .where(SourceRegistry.canonical_name == canonical_name.lower().strip())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_alias(self, alias: str) -> SourceRegistry | None:
        """Fetch the first active source whose aliases JSONB array contains the given alias."""
        alias_json = cast([alias], JSONB)
        stmt = (
            select(SourceRegistry)
            .where(
                and_(
                    SourceRegistry.aliases.op("@>")(alias_json),
                    SourceRegistry.is_active.is_(True),
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_source(self, raw_name: str) -> SourceRegistry | None:
        """Attempt to resolve a raw source string to a SourceRegistry record."""
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
    ) -> list[SourceRegistry]:
        """List active sources, optionally filtered by language."""
        stmt = select(SourceRegistry).where(SourceRegistry.is_active.is_(True))
        if language:
            stmt = stmt.where(SourceRegistry.language == language.lower())
        stmt = stmt.order_by(SourceRegistry.canonical_name.asc()).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self) -> int:
        """Return the total number of active sources."""
        from sqlalchemy import func
        stmt = (
            select(func.count())
            .select_from(SourceRegistry)
            .where(SourceRegistry.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def add_alias(self, source: SourceRegistry, alias: str) -> SourceRegistry:
        """Append a new alias to a source's aliases list if not already present."""
        current: list[str] = source.aliases or []
        if alias not in current:
            updated = current + [alias]
            return await self.update(source, aliases=updated)
        return source
