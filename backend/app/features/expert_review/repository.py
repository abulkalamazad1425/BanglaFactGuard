from __future__ import annotations

import logging
import uuid

from sqlalchemy import and_, func, select

from app.core.constants import VerificationLabel
from app.features.expert_review.models import (
    CredibilityScore,
    CredibilityWeightTier,
    ExpertProfile,
    ExpertReview,
    ExpertReviewV2,
)
from app.shared.base_repository import BaseRepository

logger = logging.getLogger(__name__)


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
            select(CredibilityScore).where(CredibilityScore.user_id == user_id).limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, user_id: uuid.UUID, initial_score: float = 0.5
    ) -> CredibilityScore:
        existing = await self.get_by_user_id(user_id)
        if existing:
            await self._sync_expert_profile(existing)
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
        await self._sync_expert_profile(record)
        return record

    async def _sync_expert_profile(self, cred: CredibilityScore) -> None:
        """Best-effort dual-write to the additive `expert_profiles` table
        (DatabaseDescription.pdf Table 4.2) so it mirrors CredibilityScore.

        Runs inside a SAVEPOINT and never raises — a failure here rolls back to
        the savepoint only, so it can never poison or abort the caller's
        outer transaction (voting/credibility flows are unaffected either way).
        """
        try:
            async with self.session.begin_nested():
                stmt = select(ExpertProfile).where(
                    ExpertProfile.user_id == cred.user_id
                )
                result = await self.session.execute(stmt)
                profile = result.scalar_one_or_none()

                if profile is None:
                    profile = ExpertProfile(
                        user_id=cred.user_id,
                        area_of_expertise="General",
                        credibility_score=cred.score,
                        total_votes=cred.total_votes,
                        correct_votes=cred.correct_votes,
                        completed_reviews_count=cred.total_votes,
                    )
                    self.session.add(profile)
                else:
                    profile.credibility_score = cred.score
                    profile.total_votes = cred.total_votes
                    profile.correct_votes = cred.correct_votes
                    profile.completed_reviews_count = cred.total_votes

                await self.session.flush()
        except Exception as exc:
            logger.warning(
                "expert_profile_sync_failed",
                extra={"user_id": str(cred.user_id), "error": str(exc)},
            )


class ExpertProfileRepository(BaseRepository[ExpertProfile]):
    """Primary credibility store post-cutover (DatabaseDescription.pdf Table 4.2).
    Replaces CredibilityScoreRepository as the store the live expert-review flow
    reads/writes; CredibilityScoreRepository above is now legacy/frozen."""

    model_class = ExpertProfile

    async def get_by_user_id(self, user_id: uuid.UUID) -> ExpertProfile | None:
        stmt = select(ExpertProfile).where(ExpertProfile.user_id == user_id).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        user_id: uuid.UUID,
        *,
        initial_score: float = 0.5,
        area_of_expertise: str = "General",
    ) -> ExpertProfile:
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            return existing
        record = ExpertProfile(
            user_id=user_id,
            area_of_expertise=area_of_expertise,
            credibility_score=initial_score,
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


class ExpertReviewV2Repository(BaseRepository[ExpertReviewV2]):

    model_class = ExpertReviewV2

    async def get_queue_for_expert(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExpertReviewV2]:
        already_voted_sub = (
            select(ExpertReviewV2.submission_id)
            .where(ExpertReviewV2.reviewer_id == expert_id)
            .scalar_subquery()
        )
        stmt = (
            select(ExpertReviewV2)
            .where(ExpertReviewV2.submission_id.not_in(already_voted_sub))
            .order_by(ExpertReviewV2.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_submission_and_reviewer(
        self, submission_id: uuid.UUID, reviewer_id: uuid.UUID
    ) -> ExpertReviewV2 | None:
        stmt = (
            select(ExpertReviewV2)
            .where(
                and_(
                    ExpertReviewV2.submission_id == submission_id,
                    ExpertReviewV2.reviewer_id == reviewer_id,
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_for_submission(
        self, submission_id: uuid.UUID
    ) -> list[ExpertReviewV2]:
        stmt = select(ExpertReviewV2).where(
            ExpertReviewV2.submission_id == submission_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_votes_for_submission(self, submission_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ExpertReviewV2)
            .where(ExpertReviewV2.submission_id == submission_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_history_for_expert(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpertReviewV2]:
        stmt = (
            select(ExpertReviewV2)
            .where(ExpertReviewV2.reviewer_id == expert_id)
            .order_by(ExpertReviewV2.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_expert(self, expert_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(ExpertReviewV2)
            .where(ExpertReviewV2.reviewer_id == expert_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
