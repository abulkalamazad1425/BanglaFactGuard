"""
app/repositories/source_repository.py
=======================================
Repository for the `source_registry` table.

Provides domain-specific query methods beyond the base CRUD operations:
- Resolve a raw claimed-source string to a canonical domain.
- Look up sources by their aliases (JSONB containment query).
- List active sources by language.

The alias resolution logic mirrors Stage 1 (Normalizer) but operates at the
DB level, making it the authoritative fallback when the static alias map in
`constants.py` does not contain the claimed source.
"""

from __future__ import annotations

import logging

from sqlalchemy import and_, cast, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_registry import SourceRegistry
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class SourceRepository(BaseRepository[SourceRegistry]):
    """
    Async repository for SourceRegistry ORM model.

    Inherits standard CRUD from BaseRepository and adds source-specific
    query methods used by SourceService and Stage 1 (Normalizer).
    """

    model_class = SourceRegistry

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ------------------------------------------------------------------
    # Domain-specific reads
    # ------------------------------------------------------------------

    async def get_by_canonical_name(self, canonical_name: str) -> SourceRegistry | None:
        """
        Fetch a source by its canonical domain name.

        Used as the primary resolution path in Stage 1 after the static
        alias map has been checked.

        Args:
            canonical_name: Lowercase domain string (e.g. "prothomalo.com").

        Returns:
            SourceRegistry instance or None if not found.
        """
        stmt = (
            select(SourceRegistry)
            .where(SourceRegistry.canonical_name == canonical_name.lower().strip())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_alias(self, alias: str) -> SourceRegistry | None:
        """
        Fetch the first active source whose `aliases` JSONB array contains
        the given alias string.

        Uses PostgreSQL's `@>` (contains) operator on the GIN-indexed
        `aliases` column for efficient lookup.

        Args:
            alias: The alias string to search for (e.g. "প্রথম আলো").

        Returns:
            The matching SourceRegistry instance or None.
        """
        # Build the containment value: '["alias_value"]' as JSONB
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
        """
        Attempt to resolve a raw source string to a SourceRegistry record.

        Resolution order:
          1. Exact match on `canonical_name` (case-insensitive).
          2. JSONB containment search on `aliases`.

        This is the DB-level counterpart to the static alias map lookup
        in Stage 1's Normalizer.

        Args:
            raw_name: Raw source string from the request or static map lookup.

        Returns:
            Resolved SourceRegistry instance or None if no match found.
        """
        normalised = raw_name.strip().lower()

        # 1. Try canonical name exact match
        source = await self.get_by_canonical_name(normalised)
        if source:
            logger.debug("Source resolved via canonical_name", extra={"raw": raw_name})
            return source

        # 2. Try alias containment
        source = await self.get_by_alias(raw_name.strip())  # preserve original case for Bangla
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
        """
        List active sources, optionally filtered by language.

        Args:
            language: Filter by language code ("bn" or "en"). None = all.
            limit:    Maximum records to return.
            offset:   Records to skip (for pagination).

        Returns:
            List of active SourceRegistry instances.
        """
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
        """
        Append a new alias to a source's aliases list if not already present.

        Args:
            source: An existing tracked SourceRegistry instance.
            alias:  The alias string to add.

        Returns:
            The updated SourceRegistry instance.
        """
        current: list[str] = source.aliases or []
        if alias not in current:
            updated = current + [alias]
            return await self.update(source, aliases=updated)
        return source
