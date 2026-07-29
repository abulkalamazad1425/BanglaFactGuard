from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.articles.models import RetrievedArticle
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ArticleRepository(BaseRepository[RetrievedArticle]):

    model_class = RetrievedArticle

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_url_hash(
        self,
        claim_id: uuid.UUID,
        url_hash: str,
    ) -> RetrievedArticle | None:
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

    async def get_for_claim(
        self,
        claim_id: uuid.UUID,
        *,
        successful_only: bool = True,
        order_by_rank: bool = True,
        limit: int = 10,
    ) -> list[RetrievedArticle]:
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
        from sqlalchemy import func

        conditions = [RetrievedArticle.claim_id == claim_id]
        if successful_only:
            conditions.append(RetrievedArticle.extraction_success.is_(True))

        stmt = (
            select(func.count()).select_from(RetrievedArticle).where(and_(*conditions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def update_rank_score(
        self,
        article_id: uuid.UUID,
        rank_score: float,
    ) -> None:
        from sqlalchemy import update

        stmt = (
            update(RetrievedArticle)
            .where(RetrievedArticle.id == article_id)
            .values(rank_score=rank_score)
        )
        await self.session.execute(stmt)
        await self.session.flush()
