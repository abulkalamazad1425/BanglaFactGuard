from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionType
from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.users.schemas import (
    ProfileResponse,
    SubmissionStatsResponse,
    SubmissionSummary,
    UpdateProfileRequest,
)
from app.features.users.service import UserAccountService
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/users", tags=["Users"])


def _service(
    request: Request, session: AsyncSession = Depends(get_async_session)
) -> UserAccountService:
    return UserAccountService(
        session, photocard_storage=getattr(request.app.state, "photocard_storage", None)
    )


@router.get("/me/submissions", response_model=list[SubmissionSummary])
async def get_my_submissions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200, description="Keyword search over headline, text and outlet"),
    state: Literal["in_progress", "review", "final", "failed"] | None = Query(default=None),
    submission_type: SubmissionType | None = Query(default=None, alias="type"),
    current_user: User = Depends(get_current_user),
    svc: UserAccountService = Depends(_service),
) -> list[SubmissionSummary]:
    return await svc.my_submissions(
        current_user, limit=limit, offset=offset, q=q, state=state, submission_type=submission_type
    )


@router.get("/me/submissions/stats", response_model=SubmissionStatsResponse)
async def get_my_submission_stats(
    current_user: User = Depends(get_current_user),
    svc: UserAccountService = Depends(_service),
) -> SubmissionStatsResponse:
    return await svc.my_submission_stats(current_user)


@router.get("/me/profile", response_model=ProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    svc: UserAccountService = Depends(_service),
) -> ProfileResponse:
    return await svc.profile(current_user)


@router.put("/me/profile", response_model=ProfileResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    svc: UserAccountService = Depends(_service),
) -> ProfileResponse:
    if current_user.role == "expert":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "expert_profile_readonly",
                "message": "Experts cannot modify their profile information. "
                "Contact an administrator to update your account details.",
            },
        )
    return await svc.update_full_name(current_user, body.full_name)
