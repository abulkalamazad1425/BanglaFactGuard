from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.security import require_role
from app.features.expert_review.repository import (
    CredibilityWeightTierRepository,
    ExpertProfileRepository,
    ExpertReviewV2Repository,
)
from app.features.expert_review.schemas import (
    CredibilityScoreResponse,
    ExpertHistoryItemResponse,
    ExpertQueueItemResponse,
    ExpertReviewResponse,
    ExpertStatsResponse,
    ExpertVoteRequest,
    ExpertVoteUpdateRequest,
)
from app.features.expert_review.service import ExpertReviewService
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.repository import ResultV2Repository
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/expert", tags=["Expert Review"])

_EXPERT_OR_ADMIN = require_role("expert", "admin")
_EXPERT_ONLY = require_role("expert")


def _get_service(
    session: AsyncSession = Depends(get_async_session),
) -> ExpertReviewService:
    return ExpertReviewService(
        review_repo=ExpertReviewV2Repository(session),
        profile_repo=ExpertProfileRepository(session),
        tier_repo=CredibilityWeightTierRepository(session),
        submission_repo=SubmissionRepository(session),
        result_repo=ResultV2Repository(session),
    )


@router.get(
    "/queue",
    response_model=list[ExpertQueueItemResponse],
    summary="Get expert review queue",
)
async def get_queue(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> list[ExpertQueueItemResponse]:
    return await svc.get_queue(current_user.id, limit=limit, offset=offset)


@router.get(
    "/queue/{submission_id}",
    response_model=ExpertQueueItemResponse,
    summary="Get a single claim for review",
)
async def get_queue_item(
    submission_id: uuid.UUID,
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertQueueItemResponse:
    return await svc.get_queue_item(submission_id)


@router.post(
    "/queue/{submission_id}/vote",
    response_model=ExpertReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit expert vote on a claim",
)
async def submit_vote(
    submission_id: uuid.UUID,
    body: ExpertVoteRequest,
    current_user: User = Depends(_EXPERT_ONLY),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertReviewResponse:
    return await svc.submit_vote(
        submission_id=submission_id,
        expert_id=current_user.id,
        expert_label=body.expert_label,
        justification=body.justification,
    )


@router.put(
    "/reviews/{review_id}",
    response_model=ExpertReviewResponse,
    summary="Edit an existing expert vote",
)
async def edit_vote(
    review_id: uuid.UUID,
    body: ExpertVoteUpdateRequest,
    current_user: User = Depends(_EXPERT_ONLY),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertReviewResponse:
    return await svc.edit_vote(
        review_id=review_id,
        expert_id=current_user.id,
        expert_label=body.expert_label,
        justification=body.justification,
    )


@router.get(
    "/history",
    response_model=list[ExpertHistoryItemResponse],
    summary="Expert vote history",
)
async def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> list[ExpertHistoryItemResponse]:
    return await svc.get_history(current_user.id, limit=limit, offset=offset)


@router.get(
    "/stats",
    response_model=ExpertStatsResponse,
    summary="Expert performance stats",
)
async def get_stats(
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertStatsResponse:
    return await svc.get_stats(current_user.id)


@router.get(
    "/credibility",
    response_model=CredibilityScoreResponse,
    summary="Current credibility score",
)
async def get_credibility(
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    session: AsyncSession = Depends(get_async_session),
) -> CredibilityScoreResponse:
    from app.core.config import get_settings

    repo = ExpertProfileRepository(session)
    profile = await repo.get_or_create(
        current_user.id,
        initial_score=get_settings().auth.initial_expert_credibility,
    )
    return CredibilityScoreResponse(
        user_id=str(profile.user_id),
        score=profile.credibility_score,
        total_votes=profile.total_votes,
        correct_votes=profile.correct_votes,
        updated_at=profile.updated_at,
    )
