from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus, VerificationLabel
from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResultV2
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/users", tags=["Users"])


class SubmissionSummary(BaseModel):
    submission_id: str
    headline: str | None
    claimed_source_text: str | None
    status: str
    ai_label: str | None
    ai_confidence: float | None
    submitted_at: datetime


class SubmissionStatsResponse(BaseModel):
    total: int
    finalized_true: int
    finalized_false: int
    finalized_partially_true: int
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
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[SubmissionSummary]:
    stmt = (
        select(Submission)
        .where(Submission.submitter_id == current_user.id)
        .order_by(Submission.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    submissions = (await session.execute(stmt)).scalars().all()
    items = []
    for submission in submissions:
        result_stmt = (
            select(VerificationResultV2)
            .where(VerificationResultV2.submission_id == submission.id)
            .limit(1)
        )
        result = (await session.execute(result_stmt)).scalar_one_or_none()
        items.append(
            SubmissionSummary(
                submission_id=str(submission.id),
                headline=submission.headline,
                claimed_source_text=submission.claimed_source_text,
                status=submission.status.value,
                ai_label=result.final_label.value if result and result.final_label else None,
                ai_confidence=result.confidence if result else None,
                submitted_at=submission.created_at,
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

    def _lc(lbl):
        return (
            select(func.count())
            .select_from(VerificationResultV2)
            .join(Submission, VerificationResultV2.submission_id == Submission.id)
            .where(
                Submission.submitter_id == current_user.id,
                VerificationResultV2.final_label == lbl,
            )
        )

    tc = (await session.execute(_lc(VerificationLabel.TRUE))).scalar_one()
    fc = (await session.execute(_lc(VerificationLabel.FALSE))).scalar_one()
    pc = (await session.execute(_lc(VerificationLabel.PARTIALLY_TRUE))).scalar_one()

    return SubmissionStatsResponse(
        total=total,
        finalized_true=tc,
        finalized_false=fc,
        finalized_partially_true=pc,
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
