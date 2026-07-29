
from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select

from app.core.constants import VerificationLabel
from app.features.expert_review.models import CredibilityScore, ExpertReview
from app.shared.base_repository import BaseRepository


class ExpertReviewRepository(BaseRepository[ExpertReview]):

    model_class = ExpertReview

    async def get_queue_for_expert(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExpertReview]:

        already_voted_sub = (
            select(ExpertReview.claim_id)
            .where(ExpertReview.reviewer_id == expert_id)
            .scalar_subquery()
        )
        stmt = (
            select(ExpertReview)
            .where(ExpertReview.claim_id.not_in(already_voted_sub))
            .order_by(ExpertReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_claim_and_reviewer(
        self, claim_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> ExpertReview | None:
        stmt = (
            select(ExpertReview)
            .where(
                and_(
                    ExpertReview.claim_id == claim_id,
                    ExpertReview.reviewer_id == reviewer_id,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_reviews_for_claim(self, claim_id: uuid.UUID) -> list[ExpertReview]:
        stmt = select(ExpertReview).where(ExpertReview.claim_id == claim_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_votes_for_claim(self, claim_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ExpertReview)
            .where(ExpertReview.claim_id == claim_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_history_for_expert(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpertReview]:
        stmt = (
            select(ExpertReview)
            .where(ExpertReview.reviewer_id == expert_id)
            .order_by(ExpertReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_expert(self, expert_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ExpertReview)
            .where(ExpertReview.reviewer_id == expert_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()


class CredibilityScoreRepository(BaseRepository[CredibilityScore]):

    model_class = CredibilityScore

    async def get_by_user_id(self, user_id: uuid.UUID) -> CredibilityScore | None:
        stmt = (
            select(CredibilityScore)
            .where(CredibilityScore.user_id == user_id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: uuid.UUID, initial_score: float = 0.5) -> CredibilityScore:
        existing = await self.get_by_user_id(user_id)
        if existing:
            return existing
        record = CredibilityScore(
            user_id=user_id,
            score=initial_score,
            total_votes=0,
            correct_votes=0,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record
