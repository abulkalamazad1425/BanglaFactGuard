"""
app/features/expert_review/router.py
========================================
Expert review API endpoints.

GET  /api/v1/expert/queue              — Paginated review queue
GET  /api/v1/expert/queue/{claim_id}   — Single claim detail for review
POST /api/v1/expert/queue/{claim_id}/vote — Submit a vote
PUT  /api/v1/expert/reviews/{review_id}   — Edit an existing vote
GET  /api/v1/expert/history            — Expert vote history
GET  /api/v1/expert/stats              — Aggregate stats
GET  /api/v1/expert/credibility        — Current credibility score

All endpoints require an authenticated user with role='expert' or 'admin'.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.security import require_role
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
    ExpertVoteRequest,
    ExpertVoteUpdateRequest,
)
from app.features.expert_review.service import ExpertReviewService
from app.features.verification.repository import ClaimRepository, ResultRepository
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/expert", tags=["Expert Review"])

_EXPERT_OR_ADMIN = require_role("expert", "admin")


def _get_service(session: AsyncSession = Depends(get_async_session)) -> ExpertReviewService:
    return ExpertReviewService(
        review_repo=ExpertReviewRepository(session),
        credibility_repo=CredibilityScoreRepository(session),
        claim_repo=ClaimRepository(session),
        result_repo=ResultRepository(session),
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
    """Return claims awaiting this expert's review."""
    return await svc.get_queue(current_user.id, limit=limit, offset=offset)


@router.get(
    "/queue/{claim_id}",
    response_model=ExpertQueueItemResponse,
    summary="Get a single claim for review",
)
async def get_queue_item(
    claim_id: uuid.UUID,
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertQueueItemResponse:
    """Return a specific claim for expert review."""
    return await svc.get_queue_item(claim_id)


@router.post(
    "/queue/{claim_id}/vote",
    response_model=ExpertReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit expert vote on a claim",
)
async def submit_vote(
    claim_id: uuid.UUID,
    body: ExpertVoteRequest,
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertReviewResponse:
    """Cast an expert verdict on a claim. Each expert may vote only once per claim."""
    return await svc.submit_vote(
        claim_id=claim_id,
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
    current_user: User = Depends(_EXPERT_OR_ADMIN),
    svc: ExpertReviewService = Depends(_get_service),
) -> ExpertReviewResponse:
    """Update a vote before the claim is finalized."""
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
    """Return all votes by the current expert with outcome information."""
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
    """Return aggregate performance statistics for the current expert."""
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
    """Return the current expert's credibility score record."""
    from app.features.expert_review.repository import CredibilityScoreRepository
    repo = CredibilityScoreRepository(session)
    from app.core.config import get_settings
    cred = await repo.get_or_create(
        current_user.id,
        initial_score=get_settings().auth.initial_expert_credibility,
    )
    return CredibilityScoreResponse(
        user_id=str(cred.user_id),
        score=cred.score,
        total_votes=cred.total_votes,
        correct_votes=cred.correct_votes,
        updated_at=cred.updated_at,
    )
