"""
app/features/expert_review/service.py
========================================
Expert review service: queue management, voting, finalization, credibility updates.

Business rules enforced here:
  - An expert cannot vote on the same claim twice.
  - Justification must be at least 50 characters.
  - A claim is finalized when MIN_EXPERT_VOTES have been cast.
  - Finalization computes a credibility-weighted verdict and updates scores.
  - Credibility scores are system-computed only — no manual override.
"""

from __future__ import annotations

import uuid
from collections import Counter

import structlog

from app.core.config import get_settings
from app.core.constants import VerificationLabel
from app.core.exceptions import DomainValidationError, PermissionDeniedError, RecordNotFoundError
from app.features.expert_review.models import CredibilityScore, ExpertReview
from app.features.expert_review.repository import (
    CredibilityScoreRepository,
    ExpertReviewRepository,
)
from app.features.expert_review.schemas import (
    CredibilityScoreResponse,
    ExpertHistoryItemResponse,
    ExpertQueueItemResponse,
    ExpertReviewResponse,
    ExpertStatsResponse,
    ExpertTopArticle,
)
from app.features.verification.repository import ClaimRepository, ResultRepository

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()
_AUTH = _SETTINGS.auth


class ExpertReviewService:
    """
    Manages the full lifecycle of expert reviews: queue, voting, and finalization.
    """

    def __init__(
        self,
        review_repo: ExpertReviewRepository,
        credibility_repo: CredibilityScoreRepository,
        claim_repo: ClaimRepository,
        result_repo: ResultRepository,
    ) -> None:
        self._reviews = review_repo
        self._credibility = credibility_repo
        self._claims = claim_repo
        self._results = result_repo

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    async def get_queue_item(
        self,
        claim_id: uuid.UUID,
    ) -> ExpertQueueItemResponse:
        """Fetch a single claim for expert review."""
        from app.core.exceptions import RecordNotFoundError
        claim = await self._claims.get_by_id(claim_id)
        if not claim:
            raise RecordNotFoundError("Claim not found.")
            
        result = await self._results.get_by_claim_id(claim_id)
        vote_count = await self._reviews.count_votes_for_claim(claim_id)

        # Build top article preview
        top_article = None
        if result and result.matched_articles:
            arts = sorted(result.matched_articles, key=lambda a: a.rank_score or 0, reverse=True)
            best = arts[0]
            top_article = ExpertTopArticle(
                url=best.url,
                title=best.title,
                published_date=str(best.published_date) if best.published_date else None,
                rank_score=best.rank_score,
                body_snippet=(best.body[:400] + '…') if best.body and len(best.body) > 400 else best.body,
            )
        
        return ExpertQueueItemResponse(
            claim_id=str(claim.id),
            headline=claim.headline,
            news_body=(claim.news_body[:600] + '…') if claim.news_body and len(claim.news_body) > 600 else claim.news_body,
            claimed_source=claim.claimed_source,
            ai_label=result.label.value if result else None,
            ai_confidence=result.confidence if result else None,
            submitted_at=claim.created_at,
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
        """
        Return completed AI-verified claims that this expert has not yet voted on.
        """
        from app.core.constants import ClaimStatus
        # Get completed claims for queue
        claims = await self._claims.get_recent(status=ClaimStatus.COMPLETED, limit=100)

        # Filter out ones this expert has already voted on
        already_voted_claim_ids = {
            r.claim_id
            for r in await self._reviews.get_history_for_expert(expert_id, limit=10000)
        }

        queue_items = []
        for claim in claims:
            if claim.id in already_voted_claim_ids:
                continue
            result = await self._results.get_by_claim_id(claim.id)
            vote_count = await self._reviews.count_votes_for_claim(claim.id)

            # Build top article for queue card preview
            top_article = None
            if result and result.matched_articles:
                arts = sorted(result.matched_articles, key=lambda a: a.rank_score or 0, reverse=True)
                best = arts[0]
                top_article = ExpertTopArticle(
                    url=best.url,
                    title=best.title,
                    published_date=str(best.published_date) if best.published_date else None,
                    rank_score=best.rank_score,
                    body_snippet=(best.body[:400] + '…') if best.body and len(best.body) > 400 else best.body,
                )

            queue_items.append(ExpertQueueItemResponse(
                claim_id=str(claim.id),
                headline=claim.headline,
                news_body=(claim.news_body[:400] + '…') if claim.news_body and len(claim.news_body) > 400 else claim.news_body,
                claimed_source=claim.claimed_source,
                ai_label=result.label.value if result else None,
                ai_confidence=result.confidence if result else None,
                submitted_at=claim.created_at,
                vote_count=vote_count,
                top_article=top_article,
            ))

        # Apply pagination
        paginated = queue_items[offset: offset + limit]
        return paginated

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    async def submit_vote(
        self,
        claim_id: uuid.UUID,
        expert_id: uuid.UUID,
        expert_label: VerificationLabel,
        justification: str,
    ) -> ExpertReviewResponse:
        """
        Cast an expert vote on a claim.

        Raises:
            RecordNotFoundError:    If the claim does not exist.
            DomainValidationError:  If the expert has already voted on this claim.
        """
        claim = await self._claims.get_by_id(claim_id)

        # Check for duplicate vote
        existing = await self._reviews.get_by_claim_and_reviewer(claim_id, expert_id)
        if existing is not None:
            raise DomainValidationError(
                message="You have already submitted a vote for this claim.",
                details={"review_id": str(existing.id)},
            )

        # Fetch current credibility score for this expert
        cred = await self._credibility.get_or_create(
            expert_id, initial_score=_AUTH.initial_expert_credibility
        )

        # Fetch AI label for reference
        result = await self._results.get_by_claim_id(claim_id)
        ai_label = result.label if result else VerificationLabel.NOT_FOUND_IN_CLAIMED_SOURCE

        review = ExpertReview(
            claim_id=claim_id,
            reviewer_id=expert_id,
            ai_label=ai_label,
            expert_label=expert_label,
            justification=justification,
            credibility_weight=cred.score,
            status="pending",
        )
        review = await self._reviews.create(review)

        logger.info(
            "expert_vote_submitted",
            review_id=str(review.id),
            claim_id=str(claim_id),
            expert_id=str(expert_id),
            label=expert_label.value,
        )

        # Auto-finalize if minimum vote threshold reached
        vote_count = await self._reviews.count_votes_for_claim(claim_id)
        if vote_count >= _AUTH.min_expert_votes_to_finalize:
            await self._finalize_claim(claim_id)

        return _review_to_response(review)

    async def edit_vote(
        self,
        review_id: uuid.UUID,
        expert_id: uuid.UUID,
        expert_label: VerificationLabel | None,
        justification: str | None,
    ) -> ExpertReviewResponse:
        """
        Update an existing vote — only allowed before the claim is finalized.

        Raises:
            RecordNotFoundError:   If the review does not exist.
            PermissionDeniedError: If the reviewer_id doesn't match.
            DomainValidationError: If the claim has already been finalized.
        """
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

    # ------------------------------------------------------------------
    # Expert History & Stats
    # ------------------------------------------------------------------

    async def get_history(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExpertHistoryItemResponse]:
        """Return all votes by this expert with final verdict comparison."""
        reviews = await self._reviews.get_history_for_expert(
            expert_id, limit=limit, offset=offset
        )
        items = []
        for r in reviews:
            claim = await self._claims.get_by_id_or_none(r.claim_id)
            result = await self._results.get_by_claim_id(r.claim_id)
            final_label = result.label.value if result else None
            matched: bool | None = None
            if final_label and r.status == "finalized":
                matched = (r.expert_label.value == final_label)
            items.append(ExpertHistoryItemResponse(
                review_id=str(r.id),
                claim_id=str(r.claim_id),
                headline=claim.headline if claim else None,
                claimed_source=claim.claimed_source if claim else None,
                expert_label=r.expert_label.value,
                ai_label=r.ai_label.value,
                final_label=final_label,
                matched=matched,
                voted_at=r.created_at,
            ))
        return items

    async def get_stats(self, expert_id: uuid.UUID) -> ExpertStatsResponse:
        """Return aggregate performance stats for an expert."""
        from app.features.auth.models import User
        cred = await self._credibility.get_or_create(
            expert_id, initial_score=_AUTH.initial_expert_credibility
        )
        user: User | None = await self._credibility.session.get(
            User, expert_id
        )
        accuracy = (
            round(cred.correct_votes / cred.total_votes * 100, 1)
            if cred.total_votes > 0
            else None
        )
        return ExpertStatsResponse(
            user_id=str(expert_id),
            full_name=user.full_name if user else None,
            total_votes=cred.total_votes,
            correct_votes=cred.correct_votes,
            accuracy_pct=accuracy,
            current_credibility=round(cred.score, 4),
        )

    # ------------------------------------------------------------------
    # Finalization (internal)
    # ------------------------------------------------------------------

    async def _finalize_claim(self, claim_id: uuid.UUID) -> None:
        """
        Compute the final weighted verdict and update expert credibility scores.

        Formula:
          1. Collect all expert votes with their credibility weights.
          2. Sum weights per label → weighted vote map.
          3. Add AI confidence to the label it predicted (weight = 1.0).
          4. Winning label = argmax of weighted totals.
          5. On a tie, the AI label wins (tiebreaker).
          6. Update credibility scores for all voting experts.
        """
        reviews = await self._reviews.get_reviews_for_claim(claim_id)
        if not reviews:
            return

        result = await self._results.get_by_claim_id(claim_id)
        if result is None:
            return

        # Weighted vote aggregation
        weighted_totals: dict[VerificationLabel, float] = {}
        for review in reviews:
            lbl = review.expert_label
            weighted_totals[lbl] = weighted_totals.get(lbl, 0.0) + review.credibility_weight

        # Add AI vote (weight = ai_confidence)
        ai_lbl = result.label
        ai_weight = result.confidence
        weighted_totals[ai_lbl] = weighted_totals.get(ai_lbl, 0.0) + ai_weight

        # Determine winner; AI wins ties
        max_weight = max(weighted_totals.values())
        winners = [l for l, w in weighted_totals.items() if w == max_weight]
        final_label = ai_lbl if ai_lbl in winners else winners[0]

        # Update result with final label (keep existing confidence — it's the AI score)
        await self._results.update(result, label=final_label)

        # Mark all reviews as finalized
        for review in reviews:
            await self._reviews.update(review, status="finalized")

        # Update credibility scores
        await self._update_credibility_scores(reviews, final_label)

        logger.info(
            "claim_finalized",
            claim_id=str(claim_id),
            final_label=final_label.value,
            vote_count=len(reviews),
        )

    async def _update_credibility_scores(
        self,
        reviews: list[ExpertReview],
        final_label: VerificationLabel,
    ) -> None:
        """
        Adjust credibility scores after finalization.

        Correct vote: score += 0.05 (up to 1.0 cap)
        Wrong vote:   score -= 0.03 (floor 0.1)
        """
        for review in reviews:
            if review.reviewer_id is None:
                continue
            cred = await self._credibility.get_or_create(review.reviewer_id)
            is_correct = review.expert_label == final_label
            delta = 0.05 if is_correct else -0.03
            new_score = max(0.1, min(1.0, cred.score + delta))
            new_correct = cred.correct_votes + (1 if is_correct else 0)
            await self._credibility.update(
                cred,
                score=round(new_score, 4),
                total_votes=cred.total_votes + 1,
                correct_votes=new_correct,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _review_to_response(r: ExpertReview) -> ExpertReviewResponse:
    return ExpertReviewResponse(
        id=str(r.id),
        claim_id=str(r.claim_id),
        reviewer_id=str(r.reviewer_id) if r.reviewer_id else None,
        ai_label=r.ai_label.value,
        expert_label=r.expert_label.value,
        justification=r.justification,
        credibility_weight=r.credibility_weight,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
