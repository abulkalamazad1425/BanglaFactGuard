from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, func, select

from app.features.expert_review.models import CredibilityWeightTier, ExpertProfile, ExpertReview, VotingConfig
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ExpertProfileRepository(BaseRepository[ExpertProfile]):
    """Storage for current expert credibility and review statistics."""

    model_class = ExpertProfile

    async def get_by_user_id(self, user_id: uuid.UUID) -> ExpertProfile | None:
        stmt = select(ExpertProfile).where(ExpertProfile.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        user_id: uuid.UUID,
        *,
        initial_score: float | None = None,  # Legacy caller compatibility; never used to seed a score.
        area_of_expertise: str = "General",
    ) -> ExpertProfile:
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            return existing
        record = ExpertProfile(
            user_id=user_id,
            area_of_expertise=area_of_expertise,
            credibility_score=None,
            total_votes=0,
            correct_votes=0,
            completed_reviews_count=0,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record


class CredibilityWeightTierRepository(BaseRepository[CredibilityWeightTier]):

    model_class = CredibilityWeightTier

    async def get_active_tiers(self) -> list[CredibilityWeightTier]:
        stmt = (
            select(CredibilityWeightTier)
            .where(CredibilityWeightTier.is_active.is_(True))
            .order_by(CredibilityWeightTier.min_accuracy_pct.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_tier_for_accuracy(
        self, accuracy_pct: float
    ) -> CredibilityWeightTier | None:
        """Find the active tier whose [min_accuracy_pct, max_accuracy_pct] range
        (inclusive both ends) contains the given accuracy percentage. Used by
        ExpertReviewService to derive each expert's voting weight — this is the
        admin-configurable replacement for the old hardcoded credibility deltas."""
        tiers = await self.get_active_tiers()
        for tier in tiers:
            if tier.min_accuracy_pct <= accuracy_pct <= tier.max_accuracy_pct:
                return tier
        return None


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
            select(ExpertReview.submission_id)
            .where(ExpertReview.reviewer_id == expert_id)
            .scalar_subquery()
        )
        stmt = (
            select(ExpertReview)
            .where(ExpertReview.submission_id.not_in(already_voted_sub))
            .order_by(ExpertReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_submission_and_reviewer(
        self, submission_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> ExpertReview | None:
        stmt = (
            select(ExpertReview)
            .where(
                and_(
                    ExpertReview.submission_id == submission_id,
                    ExpertReview.reviewer_id == reviewer_id,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_submission(
        self, submission_id: uuid.UUID
    ) -> list[ExpertReview]:
        stmt = select(ExpertReview).where(
            ExpertReview.submission_id == submission_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_votes_for_submission(self, submission_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ExpertReview)
            .where(ExpertReview.submission_id == submission_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_history_for_expert(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        q: str = "",
    ) -> list[ExpertReview]:
        stmt = (
            select(ExpertReview)
            .where(ExpertReview.reviewer_id == expert_id)
            .order_by(ExpertReview.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if q.strip():
            from sqlalchemy import or_
            from app.features.submissions.models import Submission
            term = q.strip().replace("%", r"\%").replace("_", r"\_")
            stmt = stmt.join(Submission, Submission.id == ExpertReview.submission_id).where(or_(Submission.headline.ilike(f"%{term}%", escape="\\"), Submission.claimed_source_text.ilike(f"%{term}%", escape="\\")))
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


class VotingConfigRepository(BaseRepository[VotingConfig]):
    """Single-row admin-configurable voting parameters — the oldest row is
    always the one in effect, so there is no fixed min-votes-to-finalize
    setting any more."""

    model_class = VotingConfig

    async def get_or_create(self) -> VotingConfig:
        stmt = select(VotingConfig).order_by(VotingConfig.created_at.asc()).limit(1)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            return row
        row = VotingConfig(min_expert_votes=3)
        return await self.create(row)
