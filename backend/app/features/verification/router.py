from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.constants import ClaimStatus
from app.core.exceptions import PipelineError, RecordNotFoundError
from app.features.verification.repository import ClaimRepository
from app.features.verification.schemas import (
    VerificationRequest,
    VerificationResponse,
    VerificationStatusResponse,
)
from app.features.verification.service import VerificationService
from app.features.auth.security import get_current_user_optional
from app.features.auth.models import User
from app.shared.dependencies import get_claim_repo, get_verification_service

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post(
    "",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a news claim against its claimed source",
    description=(
        "Submit a news headline and claimed source. The system searches the "
        "source's website, extracts and ranks articles, computes multi-dimensional "
        "similarity, detects manipulation, and returns a verdict: "
        "TRUE | FALSE | PARTIALLY_TRUE | NOT_FOUND_IN_CLAIMED_SOURCE."
    ),
    responses={
        200: {"description": "Verification result (may be cached)"},
        422: {"description": "Invalid request payload"},
        500: {"description": "Pipeline failure — critical stage error"},
    },
)
async def verify_claim(
    request: VerificationRequest,
    service: VerificationService = Depends(get_verification_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> VerificationResponse:
    try:
        submitter_id = current_user.id if current_user else None
        return await service.verify(request, submitter_id=submitter_id)
    except PipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "pipeline_failure",
                "message": exc.message,
                "details": exc.details,
            },
        ) from exc


@router.get(
    "/{claim_id}",
    response_model=VerificationResponse,
    summary="Get a verification result by claim ID",
    responses={
        200: {"description": "Verification result"},
        404: {"description": "Claim not found or not yet completed"},
    },
)
async def get_verification_result(
    claim_id: uuid.UUID,
    service: VerificationService = Depends(get_verification_service),
) -> VerificationResponse:
    result = await service.get_result(claim_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "claim_id": str(claim_id)},
        )
    return result


@router.get(
    "/{claim_id}/status",
    response_model=VerificationStatusResponse,
    summary="Poll the status of a verification request",
    responses={
        200: {"description": "Current pipeline status"},
        404: {"description": "Claim not found"},
    },
)
async def get_verification_status(
    claim_id: uuid.UUID,
    claim_repo: ClaimRepository = Depends(get_claim_repo),
    service: VerificationService = Depends(get_verification_service),
) -> VerificationStatusResponse:
    try:
        claim = await claim_repo.get_by_id(claim_id)
    except RecordNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "claim_id": str(claim_id)},
        )

    result = None
    if claim.status == ClaimStatus.COMPLETED:
        result = await service.get_result(claim_id)

    return VerificationStatusResponse(
        claim_id=claim_id,
        status=claim.status,
        result=result,
        error=None,
        queued_at=claim.created_at,
        updated_at=claim.updated_at,
    )
