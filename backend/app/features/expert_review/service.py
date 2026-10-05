from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar

import structlog

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineCheckStatus,
    MultimodalPredictionLabel,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.core.exceptions import (
    DomainValidationError,
    PermissionDeniedError,
)
from app.features.expert_review.models import ExpertReview, VotingConfig
from app.features.expert_review.overall_verdict import derive_ai_overall_verdict_multimodal
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
    ExpertReviewRepository,
    VotingConfigRepository,
)
from app.features.expert_review.schemas import (
    ExpertHistoryItemResponse,
    ExpertQueueItemResponse,
    ExpertReviewResponse,
    ExpertStatsResponse,
    ExpertTopArticle,
)
from app.features.verification.presenter import is_headline_result, parse_analysis
from app.features.multimodal.models import MultimodalAnalysis
from app.features.multimodal.repository import MultimodalAnalysisRepository
from app.features.multimodal.storage_service import MultimodalStorageService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.submissions.models import OcrExtraction, Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResult
from app.features.verification.repository import ResultRepository
from app.features.verification.verdict_compat import format_verdict_display

logger = structlog.get_logger(__name__)
_NEUTRAL_WEIGHT = 1.0

_STRUCTURED_TYPES = (SubmissionType.SOURCE_BASED, SubmissionType.PHOTO_CARD)

_T = TypeVar("_T")


def _tally(reviews: list[ExpertReview], get_vote: Callable[[ExpertReview], _T | None]) -> dict[_T, float]:
    """Weighted vote counts for one dimension — experts only. The AI's own
    call is never added here: per the finalization spec, T/M/margin are
    evaluated against expert consensus alone, with the AI's call used only
    as a tie-break preference (see _evaluate)."""
    weights: dict[_T, float] = {}
    for review in reviews:
        vote = get_vote(review)
        if vote is not None:
            weights[vote] = weights.get(vote, 0.0) + review.credibility_weight
    return weights


def _evaluate(
    weights: dict[_T, float], voters: int, config: VotingConfig, tie_break: _T | None
) -> tuple[bool, _T | None]:
    """Does this dimension clear ALL of: leader >= T, voters >= M,
    leader - runner_up >= margin? Returns (passes, leader) — leader is the
    current front-runner even when passes is False, so callers can still
    show "leading toward X" while a claim is under review."""
    if not weights:
        return False, tie_break
    sorted_weights = sorted(weights.values(), reverse=True)
    leader_weight = sorted_weights[0]
    runner_up_weight = sorted_weights[1] if len(sorted_weights) > 1 else 0.0
    leaders = [k for k, w in weights.items() if w == leader_weight]
    leader = tie_break if (tie_break is not None and tie_break in leaders) else leaders[0]
    passes = (
        leader_weight >= config.verified_threshold
        and voters >= config.min_expert_votes
        and (leader_weight - runner_up_weight) >= config.lead_margin
    )
    return passes, leader


class ExpertReviewService:

    def __init__(
        self,
        review_repo: ExpertReviewRepository,
        profile_repo: ExpertProfileRepository,
        tier_repo: CredibilityWeightTierRepository,
        submission_repo: SubmissionRepository,
        result_repo: ResultRepository,
        multimodal_repo: MultimodalAnalysisRepository,
        voting_config_repo: VotingConfigRepository,
        storage: MultimodalStorageService | None = None,
        photocard_storage: PhotoCardStorageService | None = None,
    ) -> None:
        self._reviews = review_repo
        self._profiles = profile_repo
        self._tiers = tier_repo
        self._submissions = submission_repo
        self._results = result_repo
        self._multimodal = multimodal_repo
        self._voting_config = voting_config_repo
        self._storage = storage
        self._photocard_storage = photocard_storage

        self._session = review_repo.session


    async def _fetch_photocard_image_url(self, submission_id: uuid.UUID) -> str | None:
        if self._photocard_storage is None:
            return None
        from sqlalchemy import select

        stmt = select(OcrExtraction).where(OcrExtraction.submission_id == submission_id)
        ocr = (await self._session.execute(stmt)).scalar_one_or_none()
        if ocr is None:
            return None
        return await self._photocard_storage.get_presigned_url(ocr.image_object_key)

    async def _fetch_top_article(self, result: VerificationResult | None) -> ExpertTopArticle | None:
        if result is None or result.top_article_id is None:
            return None
        from sqlalchemy import select
        from app.features.submissions.models import RetrievedArticle

        stmt = select(RetrievedArticle).where(
            RetrievedArticle.id == result.top_article_id
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

    @staticmethod
    def _headline_alteration_and_body(result: VerificationResult | None):
        """Headline Alteration detail + body similarity report from the
        persisted analysis blob (the same source presenter.py reads), so the
        expert view shows the identical detail after save/reload. Legacy rows
        never surface an old content verdict as a headline detail."""
        if result is None:
            return None, None
        analysis = parse_analysis(result.analysis_details)
        if analysis is None:
            return None, None
        headline = analysis.headline_alteration if is_headline_result(result) else None
        return headline, analysis.body_similarity

    async def _build_queue_item(
        self, submission: Submission, *, full_body: bool
    ) -> ExpertQueueItemResponse:
        vote_count = await self._reviews.count_votes_for_submission(submission.id)
        body_text = submission.body_text
        if not full_body and body_text and len(body_text) > 400:
            body_text = body_text[:400] + "…"

        if submission.submission_type in _STRUCTURED_TYPES:
            result = await self._results.get_by_submission_id(submission.id)
            top_article = await self._fetch_top_article(result)
            image_url = (
                await self._fetch_photocard_image_url(submission.id)
                if submission.submission_type == SubmissionType.PHOTO_CARD
                else None
            )
            headline_alteration, body_similarity = self._headline_alteration_and_body(result)
            return ExpertQueueItemResponse(
                submission_id=str(submission.id),
                submission_type=submission.submission_type,
                headline=submission.headline,
                body_text=body_text,
                claimed_source_text=submission.claimed_source_text,
                ai_label=_ai_label_structured(result),
                # No AI-implied Overall is shown to the expert for source-based/
                # photo-card claims — the automated system only ever produces
                # source/content/date status; Overall is a separate, unprompted
                # expert decision (see §6 of the business requirements).
                ai_overall_verdict=None,
                source_status=result.source_status if result else None,
                content_status=result.content_status if result and is_headline_result(result) else None,
                headline_check_status=(
                    HeadlineCheckStatus(result.headline_check_status)
                    if result and result.headline_check_status else None
                ),
                date_status=result.date_status if result else None,
                ai_confidence=result.confidence if result else None,
                submitted_at=submission.created_at,
                vote_count=vote_count,
                top_article=top_article,
                image_url=image_url,
                headline_alteration=headline_alteration,
                body_similarity=body_similarity,
            )

        mm = await self._multimodal.get_by_submission_id(submission.id)
        image_url = None
        if mm and self._storage:
            image_url = await self._storage.get_presigned_url(mm.image_object_key)
        return ExpertQueueItemResponse(
            submission_id=str(submission.id),
            submission_type=submission.submission_type,
            headline=submission.headline,
            body_text=body_text,
            claimed_source_text=submission.claimed_source_text,
            ai_label=_ai_label_multimodal(mm),
            ai_overall_verdict=derive_ai_overall_verdict_multimodal(mm.prediction) if mm else None,
            ai_confidence=(mm.confidence_fake if mm.prediction == MultimodalPredictionLabel.FAKE else mm.confidence_real) if mm else None,
            submitted_at=submission.created_at,
            vote_count=vote_count,
            image_url=image_url,
        )

    async def get_queue_item(self, submission_id: uuid.UUID) -> ExpertQueueItemResponse:
        submission = await self._submissions.get_by_id(submission_id)
        return await self._build_queue_item(submission, full_body=True)

    async def get_queue(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        q: str = "",
    ) -> list[ExpertQueueItemResponse]:
        from sqlalchemy import select, or_
        voted = select(ExpertReview.submission_id).where(ExpertReview.reviewer_id == expert_id)
        stmt = select(Submission).where(
            Submission.status == SubmissionStatus.EXPERT_REVIEW,
            Submission.duplicate_of_submission_id.is_(None),
            Submission.id.not_in(voted),
            or_(Submission.submitter_id.is_(None), Submission.submitter_id != expert_id),
        )
        if q.strip():
            term = q.strip().replace("%", r"\%").replace("_", r"\_")
            stmt = stmt.where(or_(*[c.ilike(f"%{term}%", escape="\\") for c in (Submission.headline, Submission.body_text, Submission.claimed_source_text)]))
        rows = (await self._session.execute(stmt.order_by(Submission.created_at.desc(), Submission.id.desc()).offset(offset).limit(limit))).scalars().all()
        return [await self._build_queue_item(row, full_body=False) for row in rows]

    async def submit_vote(
        self,
        submission_id: uuid.UUID,
        expert_id: uuid.UUID,
        overall_verdict: OverallVerdict,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        justification: str,
    ) -> ExpertReviewResponse:
        # Row-locks the submission for the rest of this transaction — a
        # concurrent vote on the same claim blocks here until this one
        # commits, so two simultaneous finalizing votes can't race.
        submission = await self._submissions.get_by_id_locked(submission_id)

        if submission.status != SubmissionStatus.EXPERT_REVIEW:
            raise DomainValidationError(
                message="This claim is not open for voting (already finalized, escalated, or still processing)."
            )

        if submission.submitter_id is not None and submission.submitter_id == expert_id:
            raise DomainValidationError(
                message="You cannot vote on a claim you submitted yourself."
            )

        existing = await self._reviews.get_by_submission_and_reviewer(
            submission_id, expert_id
        )
        if existing is not None:
            raise DomainValidationError(
                message="You have already submitted a vote for this claim.",
                details={"review_id": str(existing.id)},
            )

        is_structured = submission.submission_type in _STRUCTURED_TYPES

        ai_source: SourceStatus | None
        ai_content: ContentStatus | None
        ai_date: DateStatus | None

        if is_structured:
            if source_status is None:
                raise DomainValidationError(
                    message="source_status is required for this claim type."
                )
            result = await self._results.get_by_submission_id(submission_id)
            if result is None or result.source_status is None:
                raise DomainValidationError(
                    message="The AI result for this claim is not available yet."
                )
            ai_source, ai_content, ai_date = (
                result.source_status,
                result.content_status if is_headline_result(result) else None,
                result.date_status,
            )
            # No AI-implied Overall exists for this type — the automated
            # system only produces source/content/date status.
            ai_overall: OverallVerdict | None = None
        else:
            if source_status is not None:
                raise DomainValidationError(
                    message="source_status/content_status/date_status do not apply to multimodal claims."
                )
            mm = await self._multimodal.get_by_submission_id(submission_id)
            if mm is None:
                raise DomainValidationError(
                    message="The AI prediction for this claim is not available yet."
                )
            ai_source = ai_content = ai_date = None
            ai_overall = derive_ai_overall_verdict_multimodal(mm.prediction)

        config = await self._voting_config.get_or_create()
        profile = await self._profiles.get_or_create(
            expert_id
        )
        weight, tier = await self._resolve_weight(profile, config)

        review = ExpertReview(
            submission_id=submission_id,
            reviewer_id=expert_id,
            ai_overall_verdict=ai_overall,
            ai_source_status=ai_source,
            ai_content_status=ai_content,
            ai_date_status=ai_date,
            vote_overall_verdict=overall_verdict,
            vote_source_status=source_status,
            vote_content_status=content_status,
            vote_date_status=date_status,
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
            overall_verdict=overall_verdict.value,
            source_status=source_status.value if source_status else None,
            weight_applied=weight,
        )

        await self._finalize_or_escalate(submission)
        return _review_to_response(review)

    async def _resolve_weight(self, profile, config: VotingConfig):
        """Admin-configurable voting weight, resolved from credibility_weight_tiers
        by the expert's current accuracy% — replaces the old hardcoded
        ±0.05/-0.03 credibility deltas (PDF §2.2: "administrator-defined rules...
        without changing system code"). Below config.activation_threshold_votes
        (N) lifetime completed reviews, every vote counts as weight 1.0
        regardless of tier — this is `weight_applied`, snapshotted onto the
        vote row so later tier/config changes never retroactively alter it."""
        if not profile.total_votes or profile.total_votes < config.activation_threshold_votes:
            return _NEUTRAL_WEIGHT, None
        accuracy_pct = (profile.correct_votes / profile.total_votes) * 100
        tier = await self._tiers.resolve_tier_for_accuracy(accuracy_pct)
        if tier is None:
            return _NEUTRAL_WEIGHT, None
        weight = tier.weight
        if config.max_tier_weight is not None:
            weight = min(weight, config.max_tier_weight)
        return weight, tier

    async def edit_vote(
        self,
        review_id: uuid.UUID,
        expert_id: uuid.UUID,
        overall_verdict: OverallVerdict | None,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        justification: str | None,
    ) -> ExpertReviewResponse:
        review = await self._reviews.get_by_id(review_id)

        if review.reviewer_id != expert_id:
            raise PermissionDeniedError("You can only edit your own reviews.")

        if review.status == "finalized":
            raise DomainValidationError(
                message="This claim has been finalized. Votes can no longer be edited."
            )

        # Row-lock the submission too — an edit can itself tip finalization,
        # same as a fresh vote, so it needs the same concurrency guard.
        submission = await self._submissions.get_by_id_locked(review.submission_id)

        updates: dict = {}
        if overall_verdict is not None:
            updates["vote_overall_verdict"] = overall_verdict

        # source_status is only meaningful for SOURCE_BASED/PHOTO_CARD reviews
        # (review.vote_source_status is None for multimodal reviews, and stays
        # None — there's nothing to edit on that axis for them).
        if review.vote_source_status is not None or source_status is not None:
            new_source = source_status if source_status is not None else review.vote_source_status
            new_content = content_status if content_status is not None else review.vote_content_status
            new_date = date_status if date_status is not None else review.vote_date_status

            if new_source == SourceStatus.CONFIRMED:
                if new_content is None or new_date is None:
                    raise DomainValidationError(
                        message="content_status and date_status are required when source_status is CONFIRMED"
                    )
            else:
                new_content = None
                new_date = None

            updates["vote_source_status"] = new_source
            updates["vote_content_status"] = new_content
            updates["vote_date_status"] = new_date

        if justification is not None:
            updates["justification"] = justification

        if updates:
            review = await self._reviews.update(review, **updates)
            if submission.status == SubmissionStatus.EXPERT_REVIEW:
                await self._finalize_or_escalate(submission)

        return _review_to_response(review)

    async def get_history(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        q: str = "",
    ) -> list[ExpertHistoryItemResponse]:
        reviews = await self._reviews.get_history_for_expert(
            expert_id, limit=limit, offset=offset, q=q
        )
        items = []
        for r in reviews:
            submission = await self._submissions.get_by_id_or_none(r.submission_id)
            is_finalized = r.status == "finalized"

            final_overall: OverallVerdict | None = None
            final_source: SourceStatus | None = None
            final_content: ContentStatus | None = None
            final_date: DateStatus | None = None

            if is_finalized and submission is not None:
                if submission.submission_type in _STRUCTURED_TYPES:
                    result = await self._results.get_by_submission_id(r.submission_id)
                    if result is not None:
                        final_overall = result.overall_verdict
                        final_source = result.final_source_status
                        final_content = result.final_content_status
                        final_date = result.final_date_status
                else:
                    mm = await self._multimodal.get_by_submission_id(r.submission_id)
                    if mm is not None:
                        final_overall = mm.expert_overall_verdict

            matched: bool | None = None
            if is_finalized and final_overall is not None:
                matched = r.vote_overall_verdict == final_overall

            items.append(
                ExpertHistoryItemResponse(
                    review_id=str(r.id),
                    submission_id=str(r.submission_id),
                    submission_type=(
                        submission.submission_type if submission else SubmissionType.SOURCE_BASED
                    ),
                    headline=submission.headline if submission else None,
                    claimed_source_text=submission.claimed_source_text if submission else None,
                    vote_overall_verdict=r.vote_overall_verdict,
                    vote_source_status=r.vote_source_status,
                    vote_content_status=r.vote_content_status,
                    vote_date_status=r.vote_date_status,
                    ai_overall_verdict=r.ai_overall_verdict,
                    ai_source_status=r.ai_source_status,
                    ai_content_status=r.ai_content_status,
                    ai_date_status=r.ai_date_status,
                    final_overall_verdict=final_overall,
                    final_source_status=final_source,
                    final_content_status=final_content,
                    final_date_status=final_date,
                    matched=matched,
                    voted_at=r.created_at,
                )
            )
        return items

    async def get_stats(self, expert_id: uuid.UUID) -> ExpertStatsResponse:
        from app.features.auth.models import User

        profile = await self._profiles.get_or_create(
            expert_id
        )
        user: User | None = await self._profiles.session.get(User, expert_id)
        config = await self._voting_config.get_or_create()
        accuracy = (
            round(profile.correct_votes / profile.total_votes * 100, 1)
            if profile.total_votes > 0 and profile.total_votes >= config.activation_threshold_votes
            else None
        )
        return ExpertStatsResponse(
            user_id=str(expert_id),
            full_name=user.full_name if user else None,
            total_votes=profile.total_votes,
            correct_votes=profile.correct_votes,
            accuracy_pct=accuracy,
            current_credibility=(round(profile.correct_votes / profile.total_votes, 4) if profile.total_votes and profile.total_votes >= config.activation_threshold_votes else None),
            activation_threshold=config.activation_threshold_votes,
        )

    async def _finalize_or_escalate(self, submission: Submission) -> None:
        """Called after every vote cast/edit while the submission is still
        EXPERT_REVIEW. Checks every applicable dimension's T/M/margin
        condition; finalizes only if ALL of them pass simultaneously.
        Otherwise, escalates if the configured review window/vote cap has
        been exhausted. Caller must already hold the submission's row lock."""
        reviews = await self._reviews.get_for_submission(submission.id)
        if not reviews:
            return

        config = await self._voting_config.get_or_create()
        is_structured = submission.submission_type in _STRUCTURED_TYPES
        voters = len(reviews)

        if is_structured:
            result = await self._results.get_by_submission_id(submission.id)
            if result is None or result.source_status is None:
                return

            overall_weights = _tally(reviews, lambda r: r.vote_overall_verdict)
            # No AI tie-break for Overall — it is exclusively an expert
            # decision with no automated default to lean on (a true tie
            # simply fails the margin requirement and stays open).
            overall_ok, overall_leader = _evaluate(overall_weights, voters, config, None)

            source_weights = _tally(reviews, lambda r: r.vote_source_status)
            source_ok, source_leader = _evaluate(source_weights, voters, config, result.source_status)

            content_ok, date_ok = True, True
            content_leader: ContentStatus | None = None
            date_leader: DateStatus | None = None
            if source_leader == SourceStatus.CONFIRMED:
                content_weights = _tally(reviews, lambda r: r.vote_content_status)
                content_ok, content_leader = _evaluate(
                    content_weights, voters, config, result.content_status
                )
                date_weights = _tally(reviews, lambda r: r.vote_date_status)
                date_ok, date_leader = _evaluate(date_weights, voters, config, result.date_status)
            # else: source leader is NOT_FOUND (or None) -> Content/Date are
            # N/A, auto-pass, and stay unset on the finalized result.

            if overall_ok and source_ok and content_ok and date_ok and overall_leader and source_leader:
                await self._results.update(
                    result,
                    final_source_status=source_leader,
                    final_content_status=content_leader,
                    final_date_status=date_leader,
                    overall_verdict=overall_leader,
                    finalized_at=datetime.now(timezone.utc),
                )
                await self._submissions.mark_finalized(submission.id)
                for review in reviews:
                    await self._reviews.update(review, status="finalized")
                await self._update_expert_profiles(reviews, overall_leader)
                logger.info(
                    "submission_finalized",
                    submission_id=str(submission.id),
                    final_overall_verdict=overall_leader.value,
                    vote_count=voters,
                )
                return
        else:
            mm = await self._multimodal.get_by_submission_id(submission.id)
            if mm is None:
                return
            ai_overall = derive_ai_overall_verdict_multimodal(mm.prediction)
            overall_weights = _tally(reviews, lambda r: r.vote_overall_verdict)
            overall_ok, overall_leader = _evaluate(overall_weights, voters, config, ai_overall)

            if overall_ok and overall_leader:
                await self._multimodal.update(
                    mm,
                    expert_overall_verdict=overall_leader,
                    finalized_at=datetime.now(timezone.utc),
                )
                await self._submissions.mark_finalized(submission.id)
                for review in reviews:
                    await self._reviews.update(review, status="finalized")
                await self._update_expert_profiles(reviews, overall_leader)
                logger.info(
                    "submission_finalized",
                    submission_id=str(submission.id),
                    final_overall_verdict=overall_leader.value,
                    vote_count=voters,
                )
                return

        await self._maybe_escalate(submission, voters, config)

    async def _maybe_escalate(
        self, submission: Submission, voters: int, config: VotingConfig
    ) -> None:
        should_escalate = False
        if config.max_review_votes is not None and voters >= config.max_review_votes:
            should_escalate = True
        if config.max_review_hours is not None:
            age = datetime.now(timezone.utc) - submission.created_at
            if age >= timedelta(hours=config.max_review_hours):
                should_escalate = True

        if not should_escalate:
            return

        await self._submissions.set_status(submission.id, SubmissionStatus.ESCALATED)
        logger.info("submission_escalated", submission_id=str(submission.id), vote_count=voters)

    async def _update_expert_profiles(
        self,
        reviews: list[ExpertReview],
        final_overall: OverallVerdict,
    ) -> None:
        """Correctness is judged on the Overall verdict uniformly across all
        submission types — the one dimension every expert votes on, and the
        headline judgment call the platform ultimately publishes."""
        config = await self._voting_config.get_or_create()
        for review in sorted(reviews, key=lambda r: str(r.reviewer_id)):
            if review.reviewer_id is None:
                continue
            is_correct = review.vote_overall_verdict == final_overall
            profile = await self._profiles.get_or_create(review.reviewer_id)
            await self._session.refresh(profile, with_for_update=True)
            new_total = profile.total_votes + 1
            new_correct = profile.correct_votes + (1 if is_correct else 0)
            new_score = round(new_correct / new_total, 4) if new_total >= config.activation_threshold_votes else None
            await self._profiles.update(
                profile,
                total_votes=new_total,
                correct_votes=new_correct,
                credibility_score=new_score,
                completed_reviews_count=new_total,
            )


def _ai_label_structured(result: VerificationResult | None) -> str | None:
    if result is None:
        return None
    return format_verdict_display(
        result.source_status,
        result.content_status if is_headline_result(result) else None,
        result.date_status,
    )


def _ai_label_multimodal(mm: MultimodalAnalysis | None) -> str | None:
    if mm is None:
        return None
    return "Likely fake" if mm.prediction == MultimodalPredictionLabel.FAKE else "Likely real"


def _review_to_response(r: ExpertReview) -> ExpertReviewResponse:
    return ExpertReviewResponse(
        id=str(r.id),
        submission_id=str(r.submission_id),
        reviewer_id=str(r.reviewer_id) if r.reviewer_id else None,
        ai_overall_verdict=r.ai_overall_verdict,
        ai_source_status=r.ai_source_status,
        ai_content_status=r.ai_content_status,
        ai_date_status=r.ai_date_status,
        vote_overall_verdict=r.vote_overall_verdict,
        vote_source_status=r.vote_source_status,
        vote_content_status=r.vote_content_status,
        vote_date_status=r.vote_date_status,
        justification=r.justification,
        credibility_weight=r.credibility_weight,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
