from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineAlterationStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.submissions.models import OcrExtraction, Submission
from app.features.verification.presenter import effective_expert_row, effective_status, is_headline_result
from app.features.verification.headline_status import headline_status_for_result
from app.features.verification.repository import ResultRepository
from app.features.verification.models import VerificationResult
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/users", tags=["Users"])


class SubmissionSummary(BaseModel):
    """One row of My Submissions. Valid for a submission that has no result
    or even no headline yet (a just-accepted photo card)."""

    submission_id: str
    submission_type: SubmissionType = SubmissionType.SOURCE_BASED
    headline: str | None
    claimed_source_text: str | None
    status: str
    phase: str | None = None
    failure_reason: str | None = None
    source_status: SourceStatus | None
    content_status: ContentStatus | None
    headline_status: HeadlineAlterationStatus | None = None
    date_status: DateStatus | None = None
    published_date: date | None = None
    # Expert-finalized only; None while the claim is still under review.
    overall_verdict: OverallVerdict | None = None
    prediction: str | None = None
    is_finalized: bool = False
    ai_confidence: float | None
    image_url: str | None = None
    submitted_at: datetime
    updated_at: datetime | None = None


class SubmissionStatsResponse(BaseModel):
    total: int
    source_confirmed: int
    source_not_found: int
    content_matched: int
    content_altered: int
    pending: int


class ProfileResponse(BaseModel):
    id: str
    full_name: str | None
    email: str
    role: str
    is_active: bool
    is_verified: bool
    is_email_verified: bool
    avatar_url: str | None
    phone: str | None
    total_submissions: int
    bio: str | None
    verification_count: int


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=512)
    phone: str | None = Field(default=None, max_length=20)


@router.get("/me/submissions", response_model=list[SubmissionSummary])
async def get_my_submissions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[SubmissionSummary]:
    # Owner-only: only the signed-in user's own submissions, including ones
    # still PENDING/PROCESSING or FAILED and ones with no headline yet.
    stmt = (
        select(Submission)
        .where(Submission.submitter_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    submissions = (await session.execute(stmt)).scalars().all()
    result_repo = ResultRepository(session)
    from app.features.multimodal.models import MultimodalAnalysis
    photocard_storage = getattr(request.app.state, "photocard_storage", None)
    items = []
    for submission in submissions:
        result = await result_repo.get_by_submission_id(submission.id)
        expert = await effective_expert_row(submission, result, result_repo) if result else None
        is_finalized = bool(expert and expert.overall_verdict)

        mm = await session.scalar(select(MultimodalAnalysis).where(MultimodalAnalysis.submission_id == submission.id)) if submission.submission_type == SubmissionType.MULTIMODAL else None
        if mm:
            is_finalized = bool(mm.expert_overall_verdict)
        original_status = None
        if submission.duplicate_of_submission_id:
            original = (
                await session.execute(
                    select(Submission.status).where(Submission.id == submission.duplicate_of_submission_id)
                )
            ).scalar_one_or_none()
            original_status = original

        image_url = None
        if submission.submission_type == SubmissionType.PHOTO_CARD and photocard_storage:
            key = (
                await session.execute(
                    select(OcrExtraction.image_object_key).where(OcrExtraction.submission_id == submission.id)
                )
            ).scalar_one_or_none()
            if key:
                image_url = await photocard_storage.get_presigned_url(key)

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


@router.get("/me/submissions/stats", response_model=SubmissionStatsResponse)
async def get_my_submission_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> SubmissionStatsResponse:
    total = (
        await session.execute(
            select(func.count())
            .select_from(Submission)
            .where(Submission.submitter_id == current_user.id)
        )
    ).scalar_one()

    pending = (
        await session.execute(
            select(func.count())
            .select_from(Submission)
            .where(
                Submission.submitter_id == current_user.id,
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
                Submission.submitter_id == current_user.id,
                VerificationResult.source_status == status,
            )
        )

    def _cc(status: ContentStatus):
        return (
            select(func.count())
            .select_from(VerificationResult)
            .join(Submission, VerificationResult.submission_id == Submission.id)
            .where(
                Submission.submitter_id == current_user.id,
                VerificationResult.content_status == status,
            )
        )

    source_confirmed = (
        await session.execute(_sc(SourceStatus.CONFIRMED))
    ).scalar_one()
    source_not_found = (
        await session.execute(_sc(SourceStatus.NOT_FOUND))
    ).scalar_one()
    content_matched = (
        await session.execute(_cc(ContentStatus.MATCHED))
    ).scalar_one()
    content_altered = (
        await session.execute(_cc(ContentStatus.ALTERED))
    ).scalar_one()

    return SubmissionStatsResponse(
        total=total,
        source_confirmed=source_confirmed,
        source_not_found=source_not_found,
        content_matched=content_matched,
        content_altered=content_altered,
        pending=pending,
    )


@router.get("/me/profile", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ProfileResponse:
    from app.features.users.models import UserProfile

    profile = (
        await session.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id).limit(1)
        )
    ).scalar_one_or_none()
    return ProfileResponse(
        id=str(current_user.id),
        full_name=current_user.full_name,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        is_email_verified=current_user.is_email_verified,
        avatar_url=current_user.avatar_url,
        phone=current_user.phone,
        total_submissions=current_user.total_submissions,
        bio=profile.bio if profile else None,
        verification_count=profile.verification_count if profile else 0,
    )


@router.put("/me/profile", response_model=ProfileResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ProfileResponse:
    from app.features.users.models import UserProfile

    if current_user.role == "expert":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "expert_profile_readonly",
                "message": "Experts cannot modify their profile information. "
                "Contact an administrator to update your account details.",
            },
        )

    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    if body.phone is not None:
        current_user.phone = body.phone
    session.add(current_user)

    profile = (
        await session.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id).limit(1)
        )
    ).scalar_one_or_none()
    if profile and body.bio is not None:
        profile.bio = body.bio
        session.add(profile)
    await session.flush()
    return await get_my_profile(current_user, session)
