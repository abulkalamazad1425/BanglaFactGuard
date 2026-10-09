"""The signed-in user's own submissions, submission statistics and profile."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ContentStatus, SourceStatus, SubmissionStatus, SubmissionType
from app.features.auth.models import User
from app.features.multimodal.models import MultimodalAnalysis
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.submissions.models import PhotocardExtraction, Submission
from app.features.users.schemas import ProfileResponse, SubmissionStatsResponse, SubmissionSummary
from app.features.verification.headline_status import headline_status_for_result
from app.features.verification.models import VerificationResult
from app.features.verification.presenter import effective_status, is_headline_result, pick_expert_row
from app.shared.base_repository import rows_by_submission
from app.shared.utils.keyword_search import KeywordSearch


def to_profile_response(user: User, total_submissions: int) -> ProfileResponse:
    return ProfileResponse(
        id=str(user.id),
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        total_submissions=total_submissions,
        member_since=user.created_at,
    )


# My Submissions status filter -> the stored statuses behind each label the page
# shows. A duplicate still EXPERT_REVIEW whose original is FINALIZED is shown
# (and so filtered) as final - see presenter.effective_status.
MY_SUBMISSION_STATES = ("in_progress", "review", "final", "failed")


def _state_condition(state: str, original):
    dup_of_final = and_(
        Submission.duplicate_of_submission_id.is_not(None),
        Submission.status == SubmissionStatus.EXPERT_REVIEW,
        original.status == SubmissionStatus.FINALIZED,
    )
    if state == "in_progress":
        return Submission.status.in_([SubmissionStatus.PENDING, SubmissionStatus.PROCESSING])
    if state == "review":
        return and_(
            Submission.status.in_([SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.ESCALATED]),
            ~func.coalesce(dup_of_final, False),
        )
    if state == "final":
        return or_(Submission.status == SubmissionStatus.FINALIZED, func.coalesce(dup_of_final, False))
    return Submission.status == SubmissionStatus.FAILED


class UserAccountService:
    def __init__(
        self, session: AsyncSession, *, photocard_storage: PhotoCardStorageService | None = None
    ) -> None:
        self._session = session
        self._photocard_storage = photocard_storage

    async def my_submissions(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
        q: str | None = None,
        state: str | None = None,
        submission_type: SubmissionType | None = None,
    ) -> list[SubmissionSummary]:
        """Owner-only: the user's own submissions, including ones still
        PENDING/PROCESSING or FAILED and ones with no headline yet.

        Optional filters: `q` keyword search over the headline, body text and
        claimed outlet (best matches first), `state` (MY_SUBMISSION_STATES)
        and `submission_type`. Filtering happens before pagination."""
        session = self._session
        photocard_storage = self._photocard_storage
        stmt = select(Submission).where(Submission.submitter_id == user.id)
        if state in MY_SUBMISSION_STATES:
            original = aliased(Submission)
            stmt = stmt.outerjoin(original, original.id == Submission.duplicate_of_submission_id).where(
                _state_condition(state, original)
            )
        if submission_type is not None:
            stmt = stmt.where(Submission.submission_type == submission_type)
        search = KeywordSearch(
            q,
            [Submission.headline, Submission.body_text, Submission.claimed_source_text],
            headline_column=Submission.headline,
        )
        if search.active:
            stmt = stmt.where(search.condition)
        stmt = (
            stmt.order_by(*search.order_by(), Submission.created_at.desc(), Submission.id)
            .offset(offset)
            .limit(limit)
        )
        submissions = (await session.execute(stmt)).scalars().all()

        # One query per related table for the whole page (no per-row queries).
        results = await rows_by_submission(session, VerificationResult, [s.id for s in submissions])
        originals = await rows_by_submission(
            session, VerificationResult,
            list({r.reused_from_submission_id for r in results.values() if r.reused_from_submission_id}),
        )
        multimodal = await rows_by_submission(
            session, MultimodalAnalysis,
            [s.id for s in submissions if s.submission_type == SubmissionType.MULTIMODAL],
        )
        duplicate_of = list({s.duplicate_of_submission_id for s in submissions if s.duplicate_of_submission_id})
        original_statuses = (
            dict((await session.execute(
                select(Submission.id, Submission.status).where(Submission.id.in_(duplicate_of))
            )).all())
            if duplicate_of else {}
        )
        extractions = (
            await rows_by_submission(
                session, PhotocardExtraction,
                [s.id for s in submissions if s.submission_type == SubmissionType.PHOTO_CARD],
            )
            if photocard_storage else {}
        )

        items = []
        for submission in submissions:
            result = results.get(submission.id)
            expert = (
                pick_expert_row(result, originals.get(result.reused_from_submission_id))
                if result else None
            )
            is_finalized = bool(expert and expert.overall_verdict)

            mm = multimodal.get(submission.id)
            if mm:
                is_finalized = bool(mm.expert_overall_verdict)
            original_status = (
                original_statuses.get(submission.duplicate_of_submission_id)
                if submission.duplicate_of_submission_id else None
            )

            image_url = None
            extraction = extractions.get(submission.id)
            if extraction and extraction.image_object_key:
                image_url = await photocard_storage.get_presigned_url(extraction.image_object_key)

            items.append(
                SubmissionSummary(
                    submission_id=str(submission.id),
                    submission_type=submission.submission_type,
                    headline=submission.headline,
                    claimed_source_text=submission.claimed_source_text,
                    status=effective_status(submission, original_status).value,
                    phase=submission.processing_phase,
                    failure_reason=submission.failure_reason,
                    # Preliminary findings are always the AI's own calls.
                    source_status=result.source_status if result else None,
                    content_status=(result.content_status if result and is_headline_result(result) else None),
                    headline_status=headline_status_for_result(result, claim_headline=submission.headline),
                    date_status=result.date_status if result else None,
                    published_date=submission.published_date,
                    overall_verdict=mm.expert_overall_verdict if mm else expert.overall_verdict if is_finalized else None,
                    prediction=mm.prediction if mm else None,
                    is_finalized=is_finalized,
                    ai_confidence=result.confidence if result else None,
                    image_url=image_url,
                    submitted_at=submission.created_at,
                    updated_at=submission.updated_at,
                )
            )
        return items

    async def my_submission_stats(self, user: User) -> SubmissionStatsResponse:
        session = self._session
        total = (
            await session.execute(
                select(func.count())
                .select_from(Submission)
                .where(Submission.submitter_id == user.id)
            )
        ).scalar_one()

        pending = (
            await session.execute(
                select(func.count())
                .select_from(Submission)
                .where(
                    Submission.submitter_id == user.id,
                    Submission.status.in_(
                        (SubmissionStatus.PENDING, SubmissionStatus.PROCESSING)
                    ),
                )
            )
        ).scalar_one()

        def _sc(status: SourceStatus):
            return (
                select(func.count())
                .select_from(VerificationResult)
                .join(Submission, VerificationResult.submission_id == Submission.id)
                .where(
                    Submission.submitter_id == user.id,
                    VerificationResult.source_status == status,
                )
            )

        def _cc(status: ContentStatus):
            return (
                select(func.count())
                .select_from(VerificationResult)
                .join(Submission, VerificationResult.submission_id == Submission.id)
                .where(
                    Submission.submitter_id == user.id,
                    VerificationResult.content_status == status,
                )
            )

        source_confirmed = (await session.execute(_sc(SourceStatus.CONFIRMED))).scalar_one()
        source_not_found = (await session.execute(_sc(SourceStatus.NOT_FOUND))).scalar_one()
        content_matched = (await session.execute(_cc(ContentStatus.MATCHED))).scalar_one()
        content_altered = (await session.execute(_cc(ContentStatus.ALTERED))).scalar_one()

        return SubmissionStatsResponse(
            total=total,
            source_confirmed=source_confirmed,
            source_not_found=source_not_found,
            content_matched=content_matched,
            content_altered=content_altered,
            pending=pending,
        )

    async def submission_count(self, user: User) -> int:
        """Every submission the user has made, counted live - the same total
        My Submissions shows. (The cached `users.total_submissions` counter was
        only bumped for some completed checks - never for photo cards, reused
        results or failed checks - so it drifted far from the real number.)"""
        return (
            await self._session.execute(
                select(func.count()).select_from(Submission).where(Submission.submitter_id == user.id)
            )
        ).scalar_one()

    async def profile(self, user: User) -> ProfileResponse:
        return to_profile_response(user, await self.submission_count(user))

    async def update_full_name(self, user: User, full_name: str | None) -> ProfileResponse:
        if full_name is not None:
            user.full_name = full_name
        self._session.add(user)
        await self._session.flush()
        return await self.profile(user)
