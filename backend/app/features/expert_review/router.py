from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.security import require_role
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
    ExpertVoteRequest,
    ExpertVoteUpdateRequest,
)
from app.features.expert_review.service import ExpertReviewService
from app.features.multimodal.repository import MultimodalAnalysisRepository
from app.features.multimodal.storage_service import MultimodalStorageService
from app.features.photocard.storage_service import PhotoCardStorageService
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.repository import ResultRepository
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/expert", tags=["Expert Review"])

_EXPERT_OR_ADMIN = require_role("expert", "admin")
_EXPERT_ONLY = require_role("expert")


def _get_service(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> ExpertReviewService:
    storage: MultimodalStorageService | None = getattr(
        request.app.state, "multimodal_storage", None
    )
    photocard_storage: PhotoCardStorageService | None = getattr(
        request.app.state, "photocard_storage", None
    )
    return ExpertReviewService(
        review_repo=ExpertReviewRepository(session),
        profile_repo=ExpertProfileRepository(session),
        tier_repo=CredibilityWeightTierRepository(session),
        submission_repo=SubmissionRepository(session),
        result_repo=ResultRepository(session),
        multimodal_repo=MultimodalAnalysisRepository(session),
        voting_config_repo=VotingConfigRepository(session),
        storage=storage,
        photocard_storage=photocard_storage,
    )


@router.get(
    "/queue",
    response_model=list[ExpertQueueItemResponse],
    summary="Get expert review queue",
)
async def get_queue(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default="", max_length=200),
    state: Literal["all", "escalated", "review"] = Query(
        default="all",
        description="Admin queue only: all | escalated (awaiting an admin decision) | review (open, view-only).",
    ),
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> list[ExpertQueueItemResponse]:
    return await svc.get_queue(
        current_user.id, limit=limit, offset=offset, q=q, viewer_role=current_user.role, state=state
    )


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
    # Escalated claims are refused to experts here (403), not just hidden.
    return await svc.get_queue_item(
        submission_id, viewer_id=current_user.id, viewer_role=current_user.role
    )


@router.post(
    "/queue/{submission_id}/vote",
    response_model=ExpertReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a vote on a claim (experts: open claims; admins: escalated claims only)",
    description=(
        "Experts vote on claims in expert review. An administrator may vote only "
        "on an ESCALATED claim, and that overall vote becomes the final decision; "
        "on every other claim admins are view-only (403)."
    ),
)
async def submit_vote(
    submission_id: uuid.UUID,
    body: ExpertVoteRequest,
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertReviewResponse:
    return await svc.submit_vote(
        submission_id=submission_id,
        expert_id=current_user.id,
        overall_verdict=body.overall_verdict,
        source_status=body.source_status,
        content_status=body.content_status,
        date_status=body.date_status,
        justification=body.justification,
        voter_role=current_user.role,
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
        overall_verdict=body.overall_verdict,
        source_status=body.source_status,
        content_status=body.content_status,
        date_status=body.date_status,
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
    q: str = Query(default="", max_length=200),
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> list[ExpertHistoryItemResponse]:
    return await svc.get_history(current_user.id, limit=limit, offset=offset, q=q)


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
    repo = ExpertProfileRepository(session)
    profile = await repo.get_or_create(
        current_user.id,
    )
    config = await VotingConfigRepository(session).get_or_create()
    return CredibilityScoreResponse(
        user_id=str(profile.user_id),
        score=(profile.correct_votes / profile.total_votes if profile.total_votes and profile.total_votes >= config.activation_threshold_votes else None),
        total_votes=profile.total_votes,
        correct_votes=profile.correct_votes,
        updated_at=profile.updated_at,
    )
