"""
app/api/v1/endpoints/verification.py
=======================================
Verification API endpoints.

POST /api/v1/verify
    — Submit a claim for source-based verification.
    — Runs the full 12-stage pipeline (or returns cached result).
    — Returns: VerificationResponse

GET /api/v1/verify/{claim_id}
    — Retrieve a previously computed verification result by claim UUID.
    — Returns: VerificationResponse | 404

GET /api/v1/verify/{claim_id}/status
    — Lightweight status polling endpoint.
    — Returns: VerificationStatusResponse
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_claim_repo, get_verification_service
from app.core.exceptions import PipelineError, RecordNotFoundError
from app.repositories.claim_repository import ClaimRepository
from app.schemas.verification import (
    VerificationRequest,
    VerificationResponse,
    VerificationStatusResponse,
)
from app.services.verification_service import VerificationService

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
) -> VerificationResponse:
    """
    Run the 12-stage source-based verification pipeline.

    - Checks L1 (Redis) and L2 (PostgreSQL) cache first.
    - On cache miss, executes the full pipeline.
    - Returns the cached result immediately if `force_refresh=False` (default).
    """
    try:
        return await service.verify(request)
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
    """
    Retrieve a previously computed verification result by its claim UUID.
    """
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
    """
    Lightweight status check for a verification request.
    Returns the full result when status=completed.
    """
    from datetime import datetime
    try:
        claim = await claim_repo.get_by_id(claim_id)
    except RecordNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "claim_id": str(claim_id)},
        )

    from app.core.constants import ClaimStatus
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
