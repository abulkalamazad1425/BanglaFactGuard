from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, TypeVar

import structlog

from app.shared.utils.keyword_search import KeywordSearch
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
    CredibilityScoreResponse,
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
from app.features.submissions.models import PhotocardExtraction, Submission
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.models import VerificationResult
from app.features.verification.repository import ResultRepository
from app.features.verification.headline_status import headline_status_for_result
from app.features.verification.verdict_compat import format_verdict_display
from app.shared.status_labels import ai_decision_label

logger = structlog.get_logger(__name__)
_NEUTRAL_WEIGHT = 1.0

_STRUCTURED_TYPES = (SubmissionType.SOURCE_BASED, SubmissionType.PHOTO_CARD)

_T = TypeVar("_T")


def _tally(reviews: list[ExpertReview], get_vote: Callable[[ExpertReview], _T | None]) -> dict[_T, float]:
    """Weighted vote counts — experts only. Neither the AI's call nor any
    supplementary (source/headline/date) assessment is ever added."""
    weights: dict[_T, float] = {}
    for review in reviews:
        vote = get_vote(review)
        if vote is not None:
            weights[vote] = weights.get(vote, 0.0) + review.credibility_weight
    return weights


def _evaluate(
    weights: dict[_T, float], voters: int, config: VotingConfig
) -> tuple[bool, _T | None]:
    """Does the overall tally clear ALL of: a unique leader, leader >= T,
    voters >= M, leader - runner_up >= margin? Returns (passes, leader).
    `leader` is None while the top weight is tied — there is no AI or
    ordering tie-break, so a tie never finalizes (even with margin 0)."""
    if not weights:
        return False, None
    sorted_weights = sorted(weights.values(), reverse=True)
    leader_weight = sorted_weights[0]
    runner_up_weight = sorted_weights[1] if len(sorted_weights) > 1 else 0.0
    leaders = [k for k, w in weights.items() if w == leader_weight]
    leader = leaders[0] if len(leaders) == 1 else None
    passes = (
        leader is not None
        and leader_weight >= config.verified_threshold
        and voters >= config.min_expert_votes
        and (leader_weight - runner_up_weight) >= config.lead_margin
    )
    return passes, leader


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def review_limits_exceeded(
    config: VotingConfig, *, votes: int, submitted_at: datetime, now: datetime | None = None
) -> bool:
    """OR semantics: any configured limit exceeded escalates. A NULL limit is
    not configured and never counts as exceeded."""
    now = now or datetime.now(timezone.utc)
    if config.max_review_votes is not None and votes >= config.max_review_votes:
        return True
    if config.max_review_hours is not None and now - _aware(submitted_at) >= timedelta(hours=config.max_review_hours):
        return True
    return False


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

        stmt = select(PhotocardExtraction).where(PhotocardExtraction.submission_id == submission_id)
        extraction = (await self._session.execute(stmt)).scalar_one_or_none()
        if extraction is None:
            return None
        return await self._photocard_storage.get_presigned_url(extraction.image_object_key)

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
        self,
        submission: Submission,
        *,
        full_body: bool,
        viewer_id: uuid.UUID | None = None,
        viewer_role: str | None = None,
    ) -> ExpertQueueItemResponse:
        vote_count = await self._reviews.count_votes_for_submission(submission.id)
        body_text = submission.body_text
        if not full_body and body_text and len(body_text) > 400:
            body_text = body_text[:400] + "…"

        has_voted = False
        if viewer_id is not None:
            has_voted = await self._reviews.get_by_submission_and_reviewer(submission.id, viewer_id) is not None
        is_admin = viewer_role == "admin"
        if is_admin:
            can_vote = submission.status == SubmissionStatus.ESCALATED and not has_voted
        else:
            can_vote = (
                submission.status == SubmissionStatus.EXPERT_REVIEW
                and not has_voted
                and submission.submitter_id != viewer_id
            )
        common = dict(
            submission_id=str(submission.id),
            submission_type=submission.submission_type,
            status=submission.status,
            escalated_at=submission.escalated_at,
            headline=submission.headline,
            body_text=body_text,
            claimed_source_text=submission.claimed_source_text,
            published_date=submission.published_date,
            submitted_at=submission.created_at,
            vote_count=vote_count,
            has_voted=has_voted,
            can_vote=can_vote,
            decision_mode="ADMIN_FINAL" if is_admin and submission.status == SubmissionStatus.ESCALATED else "EXPERT_VOTE",
        )

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
                **common,
                ai_label=_ai_label_structured(result, submission),
                # No AI-implied Overall is shown to the expert for source-based/
                # photo-card claims — the automated system only ever produces
                # source/content/date status; Overall is a separate, unprompted
                # expert decision (see §6 of the business requirements).
                ai_overall_verdict=None,
                source_status=result.source_status if result else None,
                content_status=result.content_status if result and is_headline_result(result) else None,
                headline_status=headline_status_for_result(result, claim_headline=submission.headline),
                headline_check_status=(
                    HeadlineCheckStatus(result.headline_check_status)
                    if result and result.headline_check_status else None
                ),
                date_status=result.date_status if result else None,
                ai_confidence=result.confidence if result else None,
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
            **common,
            ai_label=_ai_label_multimodal(mm),
            ai_overall_verdict=derive_ai_overall_verdict_multimodal(mm.prediction) if mm else None,
            ai_confidence=(mm.confidence_fake if mm.prediction == MultimodalPredictionLabel.FAKE else mm.confidence_real) if mm else None,
            image_url=image_url,
        )

    async def get_queue_item(
        self,
        submission_id: uuid.UUID,
        *,
        viewer_id: uuid.UUID | None = None,
        viewer_role: str | None = None,
    ) -> ExpertQueueItemResponse:
        submission = await self._submissions.get_by_id(submission_id)
        if submission.status == SubmissionStatus.ESCALATED and viewer_role != "admin":
            # Escalated claims belong to the admin queue only.
            raise PermissionDeniedError("This claim has been escalated to an administrator for a final decision.")
        return await self._build_queue_item(
            submission, full_body=True, viewer_id=viewer_id, viewer_role=viewer_role
        )

    async def get_queue(
        self,
        expert_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        q: str = "",
        viewer_role: str = "expert",
        state: str = "all",
    ) -> list[ExpertQueueItemResponse]:
        """Experts see open (EXPERT_REVIEW) claims they have not voted on and
        did not submit — never escalated ones. Admins see the admin expert
        queue: escalated claims (theirs to decide, listed first) plus open
        claims they can only view. `state` (admin only): all | escalated | review."""
        from sqlalchemy import case, or_, select

        if viewer_role == "admin":
            statuses = {
                "escalated": (SubmissionStatus.ESCALATED,),
                "review": (SubmissionStatus.EXPERT_REVIEW,),
            }.get(state, (SubmissionStatus.ESCALATED, SubmissionStatus.EXPERT_REVIEW))
            stmt = select(Submission).where(
                Submission.status.in_(statuses),
                Submission.duplicate_of_submission_id.is_(None),
            )
            # Escalated claims first, longest-waiting first; then open claims
            # newest first, as experts see them, so recent claims (of every
            # type) are on the first page instead of behind the whole backlog.
            order = (
                case((Submission.status == SubmissionStatus.ESCALATED, 0), else_=1),
                case((Submission.status == SubmissionStatus.ESCALATED, Submission.escalated_at)).asc(),
                Submission.created_at.desc(),
                Submission.id.desc(),
            )
        else:
            voted = select(ExpertReview.submission_id).where(ExpertReview.reviewer_id == expert_id)
            stmt = select(Submission).where(
                Submission.status == SubmissionStatus.EXPERT_REVIEW,
                Submission.duplicate_of_submission_id.is_(None),
                Submission.id.not_in(voted),
                or_(Submission.submitter_id.is_(None), Submission.submitter_id != expert_id),
            )
            order = (Submission.created_at.desc(), Submission.id.desc())
        search = KeywordSearch(
            q,
            [Submission.headline, Submission.body_text, Submission.claimed_source_text],
            headline_column=Submission.headline,
        )
        if search.active:
            stmt = stmt.where(search.condition)
        rows = (
            await self._session.execute(stmt.order_by(*search.order_by(), *order).offset(offset).limit(limit))
        ).scalars().all()
        return [
            await self._build_queue_item(row, full_body=False, viewer_id=expert_id, viewer_role=viewer_role)
            for row in rows
        ]

    async def _ai_snapshot(
        self, submission: Submission
    ) -> tuple[OverallVerdict | None, SourceStatus | None, ContentStatus | None, DateStatus | None]:
        """The AI's own call at vote time, frozen onto the vote row."""
        if submission.submission_type in _STRUCTURED_TYPES:
            result = await self._results.get_by_submission_id(submission.id)
            if result is None or result.source_status is None:
                raise DomainValidationError(
                    message="The AI result for this claim is not available yet."
                )
            # No AI-implied Overall exists for this type — the automated
            # system only produces source/content/date status.
            return (
                None,
                result.source_status,
                result.content_status if is_headline_result(result) else None,
                result.date_status,
            )
        mm = await self._multimodal.get_by_submission_id(submission.id)
        if mm is None:
            raise DomainValidationError(
                message="The AI prediction for this claim is not available yet."
            )
        return derive_ai_overall_verdict_multimodal(mm.prediction), None, None, None

    @staticmethod
    def _check_supplementary(
        submission: Submission,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
    ) -> None:
        """Supplementary findings are optional and never decide anything —
        they only have to be internally consistent."""
        if submission.submission_type not in _STRUCTURED_TYPES:
            if source_status is not None or content_status is not None or date_status is not None:
                raise DomainValidationError(
                    message="source_status/content_status/date_status do not apply to multimodal claims."
                )
            return
        if source_status != SourceStatus.CONFIRMED and (content_status is not None or date_status is not None):
            raise DomainValidationError(
                message="Headline and date findings only apply when the relevant article was found in the claimed source."
            )

    async def submit_vote(
        self,
        submission_id: uuid.UUID,
        expert_id: uuid.UUID,
        overall_verdict: OverallVerdict,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        justification: str,
        *,
        voter_role: str = "expert",
    ) -> ExpertReviewResponse:
        # Row-locks the submission for the rest of this transaction — a
        # concurrent vote, admin decision or escalation sweep on the same
        # claim blocks here until this one commits, so they can't race.
        submission = await self._submissions.get_by_id_locked(submission_id)

        if voter_role == "admin":
            return await self._admin_decision(
                submission, expert_id, overall_verdict, source_status, content_status, date_status, justification
            )

        if submission.status == SubmissionStatus.ESCALATED:
            raise PermissionDeniedError(
                "This claim has been escalated. Only an administrator can decide it now."
            )
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

        self._check_supplementary(submission, source_status, content_status, date_status)
        ai_overall, ai_source, ai_content, ai_date = await self._ai_snapshot(submission)

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
            is_admin_decision=False,
        )
        review = await self._reviews.create(review)

        logger.info(
            "expert_vote_submitted",
            review_id=str(review.id),
            submission_id=str(submission_id),
            expert_id=str(expert_id),
            overall_verdict=overall_verdict.value,
            weight_applied=weight,
        )

        await self._finalize_or_escalate(submission)
        return _review_to_response(review)

    async def _admin_decision(
        self,
        submission: Submission,
        admin_id: uuid.UUID,
        overall_verdict: OverallVerdict,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        justification: str,
    ) -> ExpertReviewResponse:
        """An administrator's overall vote on an ESCALATED claim IS the final
        decision; earlier expert votes cannot override it. Every other claim is
        view-only for admins. Caller holds the submission row lock, so a second
        admin decision or a concurrent sweep sees FINALIZED and is refused."""
        if submission.status != SubmissionStatus.ESCALATED:
            raise PermissionDeniedError(
                "Administrators can only decide escalated claims. Other claims are view-only."
            )
        self._check_supplementary(submission, source_status, content_status, date_status)
        ai_overall, ai_source, ai_content, ai_date = await self._ai_snapshot(submission)

        review = await self._reviews.create(
            ExpertReview(
                submission_id=submission.id,
                reviewer_id=admin_id,
                ai_overall_verdict=ai_overall,
                ai_source_status=ai_source,
                ai_content_status=ai_content,
                ai_date_status=ai_date,
                vote_overall_verdict=overall_verdict,
                vote_source_status=source_status,
                vote_content_status=content_status,
                vote_date_status=date_status,
                justification=justification,
                credibility_weight=_NEUTRAL_WEIGHT,
                applied_weight_tier_id=None,
                status="finalized",
                is_admin_decision=True,
            )
        )
        expert_reviews = [
            r for r in await self._reviews.get_for_submission(submission.id) if not r.is_admin_decision
        ]
        await self._apply_final_decision(submission, overall_verdict, expert_reviews)
        logger.info(
            "submission_finalized_by_admin",
            submission_id=str(submission.id),
            admin_id=str(admin_id),
            final_overall_verdict=overall_verdict.value,
        )
        return _review_to_response(review)

    async def _resolve_weight(self, profile, config: VotingConfig):
        """Admin-configurable voting weight, resolved from credibility_weight_tiers
        by the expert's current accuracy% — replaces the old hardcoded
        ±0.05/-0.03 credibility deltas (PDF §2.2: "administrator-defined rules...
        without changing system code"). Below config.activation_threshold_votes
        (N) votes on claims whose final decision is complete, every vote counts as weight 1.0
        regardless of tier — this is `weight_applied`, snapshotted onto the
        vote row so later tier/config changes never retroactively alter it."""
        if not profile.total_votes or profile.total_votes < config.activation_threshold_votes:
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
        overall_verdict: OverallVerdict | None,
        source_status: SourceStatus | None,
        content_status: ContentStatus | None,
        date_status: DateStatus | None,
        justification: str | None,
    ) -> ExpertReviewResponse:
        review = await self._reviews.get_by_id(review_id)

        if review.reviewer_id != expert_id:
            raise PermissionDeniedError("You can only edit your own reviews.")

        # Row-lock the submission too — an edit can itself tip finalization,
        # same as a fresh vote, so it needs the same concurrency guard.
        submission = await self._submissions.get_by_id_locked(review.submission_id)

        if review.status == "finalized" or review.is_admin_decision or submission.status != SubmissionStatus.EXPERT_REVIEW:
            raise DomainValidationError(
                message="Votes can only be edited while the claim is in expert review (not after finalization or escalation)."
            )

        updates: dict = {}
        if overall_verdict is not None:
            updates["vote_overall_verdict"] = overall_verdict

        if review.vote_source_status is not None or source_status is not None:
            new_source = source_status if source_status is not None else review.vote_source_status
            new_content = content_status if content_status is not None else review.vote_content_status
            new_date = date_status if date_status is not None else review.vote_date_status
            if new_source != SourceStatus.CONFIRMED:
                new_content = None
                new_date = None
            self._check_supplementary(submission, new_source, new_content, new_date)
            updates["vote_source_status"] = new_source
            updates["vote_content_status"] = new_content
            updates["vote_date_status"] = new_date

        if justification is not None:
            updates["justification"] = justification

        if updates:
            review = await self._reviews.update(review, **updates)
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
            if is_finalized and submission is not None:
                if submission.submission_type in _STRUCTURED_TYPES:
                    result = await self._results.get_by_submission_id(r.submission_id)
                    if result is not None:
                        final_overall = result.overall_verdict
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
                    submission_status=submission.status if submission else None,
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
                    matched=matched,
                    is_admin_decision=bool(r.is_admin_decision),
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

    async def get_credibility(self, expert_id: uuid.UUID) -> CredibilityScoreResponse:
        """Current score (unrounded); None until the expert has cast the
        configured activation number of votes."""
        profile = await self._profiles.get_or_create(expert_id)
        config = await self._voting_config.get_or_create()
        return CredibilityScoreResponse(
            user_id=str(profile.user_id),
            score=(profile.correct_votes / profile.total_votes if profile.total_votes and profile.total_votes >= config.activation_threshold_votes else None),
            total_votes=profile.total_votes,
            correct_votes=profile.correct_votes,
            updated_at=profile.updated_at,
        )

    async def reevaluate(self, submission_id: uuid.UUID, *, now: datetime | None = None) -> bool:
        """Row-lock the submission and finalize or escalate it if its votes or
        review limits now require it (used by the escalation sweep). Returns
        True when the status changed. Caller commits."""
        submission = await self._submissions.get_by_id_locked(submission_id)
        return await self._finalize_or_escalate(submission, now=now)

    async def _finalize_or_escalate(self, submission: Submission, *, now: datetime | None = None) -> bool:
        """Re-evaluates an EXPERT_REVIEW claim after a vote, an edit or a
        sweep. Only the reviewers' OVERALL votes count — the supplementary
        source/headline/date assessments never affect the outcome. Finalizes
        when the overall tally passes; otherwise escalates when any configured
        review limit is exceeded. Returns True when the status changed.
        Caller must already hold the submission's row lock."""
        if submission.status != SubmissionStatus.EXPERT_REVIEW:
            return False
        reviews = [
            r for r in await self._reviews.get_for_submission(submission.id) if not r.is_admin_decision
        ]
        config = await self._voting_config.get_or_create()
        voters = len(reviews)

        if submission.submission_type in _STRUCTURED_TYPES:
            result = await self._results.get_by_submission_id(submission.id)
            if result is None or result.source_status is None:
                return False
        else:
            mm = await self._multimodal.get_by_submission_id(submission.id)
            if mm is None:
                return False

        overall_ok, overall_leader = _evaluate(
            _tally(reviews, lambda r: r.vote_overall_verdict), voters, config
        )
        if overall_ok and overall_leader is not None:
            await self._apply_final_decision(submission, overall_leader, reviews)
            logger.info(
                "submission_finalized",
                submission_id=str(submission.id),
                final_overall_verdict=overall_leader.value,
                vote_count=voters,
            )
            return True

        return await self._maybe_escalate(submission, voters, config, now=now)

    async def _apply_final_decision(
        self,
        submission: Submission,
        final_overall: OverallVerdict,
        expert_reviews: list[ExpertReview],
    ) -> None:
        """Writes the final overall verdict. The AI's own columns and the
        legacy final_source/content/date columns are left untouched — the
        supplementary assessments are never promoted into a finding."""
        now = datetime.now(timezone.utc)
        if submission.submission_type in _STRUCTURED_TYPES:
            result = await self._results.get_by_submission_id(submission.id)
            await self._results.update(result, overall_verdict=final_overall, finalized_at=now)
        else:
            mm = await self._multimodal.get_by_submission_id(submission.id)
            await self._multimodal.update(mm, expert_overall_verdict=final_overall, finalized_at=now)
        await self._submissions.mark_finalized(submission.id)
        submission.status = SubmissionStatus.FINALIZED
        for review in expert_reviews:
            await self._reviews.update(review, status="finalized")
        await self._update_expert_profiles(expert_reviews)

    async def _maybe_escalate(
        self,
        submission: Submission,
        voters: int,
        config: VotingConfig,
        *,
        now: datetime | None = None,
    ) -> bool:
        if not review_limits_exceeded(config, votes=voters, submitted_at=submission.created_at, now=now):
            return False
        # Conditional transition: only the transaction that actually moves the
        # claim out of EXPERT_REVIEW notifies, so admins are told exactly once.
        if not await self._submissions.escalate_if_open(submission.id):
            return False
        submission.status = SubmissionStatus.ESCALATED
        logger.info("submission_escalated", submission_id=str(submission.id), vote_count=voters)
        from app.features.expert_review.escalation import notify_admins_of_escalation

        await notify_admins_of_escalation(self._session, submission)
        return True

    async def _update_expert_profiles(self, reviews: list[ExpertReview]) -> None:
        """Correctness is judged on the Overall verdict uniformly across all
        submission types — the one dimension every expert votes on, and the
        headline judgment call the platform ultimately publishes. An admin's
        own decision row is never scored.

        A vote counts towards N (activation_threshold_votes) and accuracy only
        once its claim's final decision is complete. The counters are re-derived
        from the finalized claims rather than incremented, so they cannot drift
        (an incremented counter kept counting votes on claims later deleted)."""
        config = await self._voting_config.get_or_create()
        await self._session.flush()
        for review in sorted(reviews, key=lambda r: str(r.reviewer_id)):
            if review.reviewer_id is None or review.is_admin_decision:
                continue
            profile = await self._profiles.get_or_create(review.reviewer_id)
            await self._session.refresh(profile, with_for_update=True)
            await self._profiles.refresh_stats(profile, config.activation_threshold_votes)


def _ai_label_structured(result: VerificationResult | None, submission: Submission | None = None) -> str | None:
    if result is None:
        return None
    return format_verdict_display(
        result.source_status,
        headline_status_for_result(result, claim_headline=submission.headline if submission else None),
        result.date_status,
    )


def _ai_label_multimodal(mm: MultimodalAnalysis | None) -> str | None:
    if mm is None:
        return None
    return ai_decision_label(mm.prediction)


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
        is_admin_decision=bool(r.is_admin_decision),
        created_at=r.created_at,
        updated_at=r.updated_at,
    )
