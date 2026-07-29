from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.admin.schemas import (
    AdminStatsResponse,
    CreateExpertRequest,
    ExpertResponse,
    ResetExpertPasswordRequest,
    UpdateExpertRequest,
)
from app.features.admin.service import AdminService
from app.features.auth.models import User
from app.features.auth.repository import RefreshTokenRepository, UserRepository
from app.features.auth.security import require_role
from app.features.expert_review.repository import CredibilityScoreRepository
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/admin", tags=["Admin"])
_ADMIN_ONLY = require_role("admin")


def _get_service(session: AsyncSession = Depends(get_async_session)) -> AdminService:
    return AdminService(
        session=session,
        user_repo=UserRepository(session),
        credibility_repo=CredibilityScoreRepository(session),
        token_repo=RefreshTokenRepository(session),
    )


@router.post(
    "/experts",
    response_model=ExpertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an expert account",
)
async def create_expert(
    body: CreateExpertRequest,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> ExpertResponse:
    return await svc.create_expert(body)


@router.get(
    "/experts",
    response_model=list[ExpertResponse],
    summary="List all expert accounts",
)
async def list_experts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> list[ExpertResponse]:
    return await svc.list_experts(limit=limit, offset=offset)


@router.get(
    "/experts/{expert_id}",
    response_model=ExpertResponse,
    summary="Get a single expert account",
)
async def get_expert(
    expert_id: uuid.UUID,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> ExpertResponse:
    return await svc.get_expert(expert_id)


@router.put(
    "/experts/{expert_id}",
    response_model=ExpertResponse,
    summary="Update expert profile (name, email, expertise, active status)",
)
async def update_expert(
    expert_id: uuid.UUID,
    body: UpdateExpertRequest,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> ExpertResponse:
    return await svc.update_expert(expert_id, body)


@router.post(
    "/experts/{expert_id}/reset-password",
    summary="Admin resets expert password",
)
async def reset_expert_password(
    expert_id: uuid.UUID,
    body: ResetExpertPasswordRequest,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> dict:
    return await svc.reset_expert_password(expert_id, body)


@router.post(
    "/experts/{expert_id}/deactivate",
    response_model=ExpertResponse,
    summary="Deactivate an expert account",
)
async def deactivate_expert(
    expert_id: uuid.UUID,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> ExpertResponse:
    return await svc.deactivate_expert(expert_id)


@router.post(
    "/experts/{expert_id}/activate",
    response_model=ExpertResponse,
    summary="Re-activate an expert account",
)
async def activate_expert(
    expert_id: uuid.UUID,
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> ExpertResponse:
    return await svc.activate_expert(expert_id)


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Platform-wide statistics",
)
async def get_platform_stats(
    _: User = Depends(_ADMIN_ONLY),
    svc: AdminService = Depends(_get_service),
) -> AdminStatsResponse:
    return await svc.get_platform_stats()
