"""
app/features/sources/service.py
=================================
Application service for source registry CRUD operations.

Migrated from: app/services/source_service.py
"""

from __future__ import annotations

import math
import uuid

from app.core.exceptions import DuplicateRecordError, RecordNotFoundError
from app.features.sources.models import VerifiedSource
from app.features.sources.repository import SourceRepository
from app.features.sources.schemas import (
    SourceCreateSchema,
    SourceListSchema,
    SourceResponseSchema,
    SourceUpdateSchema,
)


class SourceService:
    """CRUD service for the source_registry table."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self.source_repo = source_repo

    async def create_source(self, payload: SourceCreateSchema) -> SourceResponseSchema:
        """Create a new source. Raises DuplicateRecordError if canonical_name exists."""
        existing = await self.source_repo.get_by_canonical_name(payload.canonical_name)
        if existing:
            raise DuplicateRecordError(
                model="VerifiedSource",
                field="canonical_name",
                value=payload.canonical_name,
            )
        source = VerifiedSource(
            canonical_name=payload.canonical_name,
            display_name=payload.display_name,
            aliases=payload.aliases,
            base_url=payload.base_url,
            rss_url=payload.rss_url,
            language=payload.language,
            description=payload.description,
            body_selectors=payload.body_selectors,
            title_selectors=payload.title_selectors,
            date_selectors=payload.date_selectors,
            internal_search_url=payload.internal_search_url,
            article_url_patterns=payload.article_url_patterns,
            is_active=True,
        )
        created = await self.source_repo.create(source)
        return SourceResponseSchema.model_validate(created)

    async def get_source(self, source_id: uuid.UUID) -> SourceResponseSchema:
        """Fetch a source by UUID. Raises RecordNotFoundError if absent."""
        source = await self.source_repo.get_by_id(source_id)
        return SourceResponseSchema.model_validate(source)

    async def update_source(
        self, source_id: uuid.UUID, payload: SourceUpdateSchema
    ) -> SourceResponseSchema:
        """Partially update a source. Only non-None fields are applied."""
        source = await self.source_repo.get_by_id(source_id)
        update_fields = payload.model_dump(exclude_none=True)
        if update_fields:
            source = await self.source_repo.update(source, **update_fields)
        return SourceResponseSchema.model_validate(source)

    async def delete_source(self, source_id: uuid.UUID) -> None:
        """Hard-delete a source record."""
        await self.source_repo.delete_by_id(source_id)

    async def list_sources(
        self,
        *,
        language: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> SourceListSchema:
        """Return a paginated list of active sources."""
        offset = (page - 1) * size
        items = await self.source_repo.list_active(
            language=language, limit=size, offset=offset
        )
        total = await self.source_repo.count_active()
        pages = math.ceil(total / size) if size else 0
        return SourceListSchema(
            items=[SourceResponseSchema.model_validate(s) for s in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
