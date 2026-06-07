"""
app/repositories/article_repository.py
========================================
Repository for the `retrieved_articles` table.

Handles storage and retrieval of candidate articles fetched during Stages 5–7.

Key concerns:
- URL deduplication via `url_hash`: prevents processing the same article URL
  twice within a single claim (e.g. if Brave and Google RSS both return it).
- Batch insertion: Stage 12 inserts all retrieved articles for a claim in one
  `bulk_create` call, so the batch path is optimised.
- Retrieval ordering: downstream stages (8–10) always want articles sorted by
  `rank_score DESC` to process the best evidence first.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieved_article import RetrievedArticle
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ArticleRepository(BaseRepository[RetrievedArticle]):
    """
    Async repository for RetrievedArticle ORM model.

    Inherits standard CRUD from BaseRepository and adds article-specific
    query methods used by Stage 12 (Persistence) and Stage 7 (Ranker).
    """

    model_class = RetrievedArticle

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    async def get_by_url_hash(
        self,
        claim_id: uuid.UUID,
        url_hash: str,
    ) -> RetrievedArticle | None:
        """
        Check whether a URL has already been retrieved for this claim.

        Uses the composite unique index `(claim_id, url_hash)` for an
        efficient point lookup — avoids re-processing duplicate URLs when
        multiple query variants return the same article.

        Args:
            claim_id: UUID of the parent claim.
            url_hash: SHA-256 hex digest of the article URL.

        Returns:
            Existing RetrievedArticle instance or None (URL is new).
        """
        stmt = (
            select(RetrievedArticle)
            .where(
                and_(
                    RetrievedArticle.claim_id == claim_id,
                    RetrievedArticle.url_hash == url_hash,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def url_already_retrieved(
        self,
        claim_id: uuid.UUID,
        url_hash: str,
    ) -> bool:
        """
        Return True if a URL has already been retrieved for this claim.

        More efficient than `get_by_url_hash` when only a boolean is needed
        (issues a COUNT(1) query instead of fetching the full row).

        Args:
            claim_id: UUID of the parent claim.
            url_hash: SHA-256 hex of the article URL.

        Returns:
            True if the URL already exists for this claim.
        """
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(RetrievedArticle)
            .where(
                and_(
                    RetrievedArticle.claim_id == claim_id,
                    RetrievedArticle.url_hash == url_hash,
                )
            )
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0

    # ------------------------------------------------------------------
    # Claim-scoped queries
    # ------------------------------------------------------------------

    async def get_for_claim(
        self,
        claim_id: uuid.UUID,
        *,
        successful_only: bool = True,
        order_by_rank: bool = True,
        limit: int = 10,
    ) -> list[RetrievedArticle]:
        """
        Retrieve all articles associated with a claim.

        The primary read path for Stages 8–10 which need the ranked
        evidence candidates for a specific claim.

        Args:
            claim_id:        UUID of the parent claim.
            successful_only: If True, only return articles where extraction_success=True.
            order_by_rank:   If True, order by rank_score DESC (best evidence first).
            limit:           Maximum articles to return.

        Returns:
            List of RetrievedArticle instances.
        """
        conditions = [RetrievedArticle.claim_id == claim_id]
        if successful_only:
            conditions.append(RetrievedArticle.extraction_success.is_(True))

        stmt = select(RetrievedArticle).where(and_(*conditions))

        if order_by_rank:
            stmt = stmt.order_by(RetrievedArticle.rank_score.desc().nullslast())

        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_top_ranked(
        self,
        claim_id: uuid.UUID,
    ) -> RetrievedArticle | None:
        """
        Return the single highest-ranked successfully extracted article for a claim.

        Used by Stage 11 (Classifier) and Stage 12 (Persistence) to identify
        the primary evidence article for the verdict.

        Args:
            claim_id: UUID of the parent claim.

        Returns:
            The highest-ranked RetrievedArticle or None if none were extracted.
        """
        stmt = (
            select(RetrievedArticle)
            .where(
                and_(
                    RetrievedArticle.claim_id == claim_id,
                    RetrievedArticle.extraction_success.is_(True),
                )
            )
            .order_by(RetrievedArticle.rank_score.desc().nullslast())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_for_claim(
        self,
        claim_id: uuid.UUID,
        *,
        successful_only: bool = False,
    ) -> int:
        """
        Count articles retrieved for a claim.

        Args:
            claim_id:        UUID of the parent claim.
            successful_only: If True, count only successfully extracted articles.

        Returns:
            Integer count.
        """
        from sqlalchemy import func

        conditions = [RetrievedArticle.claim_id == claim_id]
        if successful_only:
            conditions.append(RetrievedArticle.extraction_success.is_(True))

        stmt = (
            select(func.count())
            .select_from(RetrievedArticle)
            .where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_rank_score(
        self,
        article_id: uuid.UUID,
        rank_score: float,
    ) -> None:
        """
        Update the rank_score of a specific article using a direct UPDATE.

        Called by Stage 7 (Ranker) after computing per-article scores.
        Uses a direct UPDATE (not fetch + modify) for efficiency.

        Args:
            article_id: UUID of the article to update.
            rank_score: New rank score in [0.0, 1.0].
        """
        from sqlalchemy import update

        stmt = (
            update(RetrievedArticle)
            .where(RetrievedArticle.id == article_id)
            .values(rank_score=rank_score)
        )
        await self.session.execute(stmt)
        await self.session.flush()
