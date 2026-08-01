from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ClaimStatus, VerificationLabel
from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.verification.models import VerificationResult, VerifiedClaim
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/users", tags=["Users"])


class SubmissionSummary(BaseModel):
    claim_id: str
    headline: str
    claimed_source: str
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
    bio: str | None
    verification_count: int


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=1000)


@router.get("/me/submissions", response_model=list[SubmissionSummary])
async def get_my_submissions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[SubmissionSummary]:
    stmt = (
        select(VerifiedClaim)
        .where(VerifiedClaim.submitter_id == current_user.id)
        .order_by(VerifiedClaim.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    claims = (await session.execute(stmt)).scalars().all()
    items = []
    for claim in claims:
        result_stmt = (
            select(VerificationResult)
            .where(VerificationResult.claim_id == claim.id)
            .limit(1)
        )
        result = (await session.execute(result_stmt)).scalar_one_or_none()
        items.append(
            SubmissionSummary(
                claim_id=str(claim.id),
                headline=claim.headline,
                claimed_source=claim.claimed_source,
                status=claim.status.value,
                ai_label=result.label.value if result else None,
                ai_confidence=result.confidence if result else None,
                submitted_at=claim.created_at,
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
            .select_from(VerifiedClaim)
            .where(VerifiedClaim.submitter_id == current_user.id)
        )
    ).scalar_one()

    pending = (
        await session.execute(
            select(func.count())
            .select_from(VerifiedClaim)
            .where(
                VerifiedClaim.submitter_id == current_user.id,
                VerifiedClaim.status == ClaimStatus.PENDING,
            )
        )
    ).scalar_one()

    def _lc(lbl):
        return (
            select(func.count())
            .select_from(VerificationResult)
            .join(VerifiedClaim, VerificationResult.claim_id == VerifiedClaim.id)
            .where(
                VerifiedClaim.submitter_id == current_user.id,
                VerificationResult.label == lbl,
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
