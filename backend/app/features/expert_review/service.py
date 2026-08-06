from __future__ import annotations

import uuid

import structlog

from app.core.config import get_settings
from app.core.constants import SubmissionStatus, VerificationLabel
from app.core.exceptions import (
    DomainValidationError,
    PermissionDeniedError,
    RecordNotFoundError,
)
from app.features.expert_review.models import ExpertReviewV2
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
    ExpertReviewV2Repository,
)
from app.features.expert_review.schemas import (
    ExpertHistoryItemResponse,
    ExpertQueueItemResponse,
    ExpertReviewResponse,
    ExpertStatsResponse,
    ExpertTopArticle,
)
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.repository import ResultV2Repository

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()
_AUTH = _SETTINGS.auth
_NEUTRAL_WEIGHT = 1.0


class ExpertReviewService:

    def __init__(
        self,
        review_repo: ExpertReviewV2Repository,
        profile_repo: ExpertProfileRepository,
        tier_repo: CredibilityWeightTierRepository,
        submission_repo: SubmissionRepository,
        result_repo: ResultV2Repository,
    ) -> None:
        self._reviews = review_repo
        self._profiles = profile_repo
        self._tiers = tier_repo
        self._submissions = submission_repo
        self._results = result_repo

        self._session = review_repo.session

    async def _fetch_top_article(self, result) -> ExpertTopArticle | None:
        if result is None or result.top_article_id is None:
            return None
        from sqlalchemy import select
        from app.features.submissions.models import RetrievedArticleV2

        stmt = select(RetrievedArticleV2).where(
            RetrievedArticleV2.id == result.top_article_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        body = row.body
        return ExpertTopArticle(
            url=row.url,
            title=row.title,
            published_date=str(row.published_date) if row.published_date else None,
            rank_score=row.rank_score,
            body_snippet=(body[:400] + "…") if body and len(body) > 400 else body,
        )

    async def get_queue_item(
        self,
        submission_id: uuid.UUID,
    ) -> ExpertQueueItemResponse:
        submission = await self._submissions.get_by_id(submission_id)

        result = await self._results.get_by_submission_id(submission_id)
        vote_count = await self._reviews.count_votes_for_submission(submission_id)
        top_article = await self._fetch_top_article(result)

        return ExpertQueueItemResponse(
            submission_id=str(submission.id),
            headline=submission.headline,
            # Full, untruncated body — the review-detail page needs the
            # complete submitted claim text, unlike the queue list preview.
            body_text=submission.body_text,
            claimed_source_text=submission.claimed_source_text,
            ai_label=result.final_label.value if result and result.final_label else None,
            ai_confidence=result.confidence if result else None,
            submitted_at=submission.created_at,
            vote_count=vote_count,
            top_article=top_article,
        )

    async def get_queue(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExpertQueueItemResponse]:
        submissions = await self._submissions.get_recent(
            status=SubmissionStatus.EXPERT_REVIEW, limit=100
        )

        already_voted_ids = {
            r.submission_id
            for r in await self._reviews.get_history_for_expert(expert_id, limit=10000)
        }

        queue_items = []
        for submission in submissions:
            if submission.id in already_voted_ids:
                continue
            result = await self._results.get_by_submission_id(submission.id)
            vote_count = await self._reviews.count_votes_for_submission(submission.id)
            top_article = await self._fetch_top_article(result)

            queue_items.append(
                ExpertQueueItemResponse(
                    submission_id=str(submission.id),
                    headline=submission.headline,
                    body_text=(
                        (submission.body_text[:400] + "…")
                        if submission.body_text and len(submission.body_text) > 400
                        else submission.body_text
                    ),
                    claimed_source_text=submission.claimed_source_text,
                    ai_label=(
                        result.final_label.value
                        if result and result.final_label
                        else None
                    ),
                    ai_confidence=result.confidence if result else None,
                    submitted_at=submission.created_at,
                    vote_count=vote_count,
                    top_article=top_article,
                )
            )

        paginated = queue_items[offset : offset + limit]
        return paginated

    async def submit_vote(
        self,
        submission_id: uuid.UUID,
        expert_id: uuid.UUID,
        expert_label: VerificationLabel,
        justification: str,
    ) -> ExpertReviewResponse:
        await self._submissions.get_by_id(submission_id)

        existing = await self._reviews.get_by_submission_and_reviewer(
            submission_id, expert_id
        )
        if existing is not None:
            raise DomainValidationError(
                message="You have already submitted a vote for this claim.",
                details={"review_id": str(existing.id)},
            )

        profile = await self._profiles.get_or_create(
            expert_id, initial_score=_AUTH.initial_expert_credibility
        )
        weight, tier = await self._resolve_weight(profile)

        result = await self._results.get_by_submission_id(submission_id)
        ai_label = (
            result.final_label
            if result and result.final_label
            else VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE
        )

        review = ExpertReviewV2(
            submission_id=submission_id,
            reviewer_id=expert_id,
            ai_label=ai_label.value,
            expert_label=expert_label,
            justification=justification,
            credibility_weight=weight,
            applied_weight_tier_id=tier.id if tier else None,
            status="pending",
        )
        review = await self._reviews.create(review)

        logger.info(
            "expert_vote_submitted",
            review_id=str(review.id),
            submission_id=str(submission_id),
            expert_id=str(expert_id),
            label=expert_label.value,
            weight=weight,
        )

        vote_count = await self._reviews.count_votes_for_submission(submission_id)
        if vote_count >= _AUTH.min_expert_votes_to_finalize:
            await self._finalize_submission(submission_id)

        return _review_to_response(review)

    async def _resolve_weight(self, profile):
        """Admin-configurable voting weight, resolved from credibility_weight_tiers
        by the expert's current accuracy% — replaces the old hardcoded
        ±0.05/-0.03 credibility deltas (PDF §2.2: "administrator-defined rules...
        without changing system code")."""
        if profile.total_votes <= 0:
            return _NEUTRAL_WEIGHT, None
        accuracy_pct = (profile.correct_votes / profile.total_votes) * 100
        tier = await self._tiers.resolve_tier_for_accuracy(accuracy_pct)
        if tier is None:
            return _NEUTRAL_WEIGHT, None
        return tier.weight, tier

    async def edit_vote(
        self,
        review_id: uuid.UUID,
        expert_id: uuid.UUID,
        expert_label: VerificationLabel | None,
        justification: str | None,
    ) -> ExpertReviewResponse:
        review = await self._reviews.get_by_id(review_id)

        if review.reviewer_id != expert_id:
            raise PermissionDeniedError("You can only edit your own reviews.")

        if review.status == "finalized":
            raise DomainValidationError(
                message="This claim has been finalized. Votes can no longer be edited."
            )

        updates: dict = {}
        if expert_label is not None:
            updates["expert_label"] = expert_label
        if justification is not None:
            updates["justification"] = justification

        if updates:
            review = await self._reviews.update(review, **updates)

        return _review_to_response(review)

    async def get_history(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpertHistoryItemResponse]:
        reviews = await self._reviews.get_history_for_expert(
            expert_id, limit=limit, offset=offset
        )
        items = []
        for r in reviews:
            submission = await self._submissions.get_by_id_or_none(r.submission_id)
            result = await self._results.get_by_submission_id(r.submission_id)
            final_label = result.final_label.value if result and result.final_label else None
            matched: bool | None = None
            if final_label and r.status == "finalized":
                matched = r.expert_label.value == final_label
            items.append(
                ExpertHistoryItemResponse(
                    review_id=str(r.id),
                    submission_id=str(r.submission_id),
                    headline=submission.headline if submission else None,
                    claimed_source_text=submission.claimed_source_text if submission else None,
                    expert_label=r.expert_label.value,
                    ai_label=r.ai_label,
                    final_label=final_label,
                    matched=matched,
                    voted_at=r.created_at,
                )
            )
        return items

    async def get_stats(self, expert_id: uuid.UUID) -> ExpertStatsResponse:
        from app.features.auth.models import User

        profile = await self._profiles.get_or_create(
            expert_id, initial_score=_AUTH.initial_expert_credibility
        )
        user: User | None = await self._profiles.session.get(User, expert_id)
        accuracy = (
            round(profile.correct_votes / profile.total_votes * 100, 1)
            if profile.total_votes > 0
            else None
        )
        return ExpertStatsResponse(
            user_id=str(expert_id),
            full_name=user.full_name if user else None,
            total_votes=profile.total_votes,
            correct_votes=profile.correct_votes,
            accuracy_pct=accuracy,
            current_credibility=round(profile.credibility_score, 4),
        )

    async def _finalize_submission(self, submission_id: uuid.UUID) -> None:
        reviews = await self._reviews.get_for_submission(submission_id)
        if not reviews:
            return

        result = await self._results.get_by_submission_id(submission_id)
        if result is None or result.final_label is None:
            return

        weighted_totals: dict[VerificationLabel, float] = {}
        for review in reviews:
            lbl = review.expert_label
            weighted_totals[lbl] = (
                weighted_totals.get(lbl, 0.0) + review.credibility_weight
            )

        ai_lbl = result.final_label
        ai_weight = result.confidence or 0.0
        weighted_totals[ai_lbl] = weighted_totals.get(ai_lbl, 0.0) + ai_weight

        max_weight = max(weighted_totals.values())
        winners = [l for l, w in weighted_totals.items() if w == max_weight]
        final_label = ai_lbl if ai_lbl in winners else winners[0]

        await self._results.update(result, final_label=final_label)
        await self._submissions.mark_finalized(submission_id)

        for review in reviews:
            await self._reviews.update(review, status="finalized")

        await self._update_expert_profiles(reviews, final_label)

        logger.info(
            "submission_finalized",
            submission_id=str(submission_id),
            final_label=final_label.value,
            vote_count=len(reviews),
        )

    async def _update_expert_profiles(
        self,
        reviews: list[ExpertReviewV2],
        final_label: VerificationLabel,
    ) -> None:
        for review in reviews:
            if review.reviewer_id is None:
                continue
            profile = await self._profiles.get_or_create(review.reviewer_id)
            is_correct = review.expert_label == final_label
            new_total = profile.total_votes + 1
            new_correct = profile.correct_votes + (1 if is_correct else 0)
            new_score = round(new_correct / new_total, 4) if new_total else 0.5
            await self._profiles.update(
                profile,
                total_votes=new_total,
                correct_votes=new_correct,
                credibility_score=new_score,
                completed_reviews_count=new_total,
            )


def _review_to_response(r: ExpertReviewV2) -> ExpertReviewResponse:
    return ExpertReviewResponse(
        id=str(r.id),
        submission_id=str(r.submission_id),
        reviewer_id=str(r.reviewer_id) if r.reviewer_id else None,
        ai_label=r.ai_label,
        expert_label=r.expert_label.value,
        justification=r.justification,
        credibility_weight=r.credibility_weight,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
