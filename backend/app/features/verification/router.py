from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.constants import SubmissionStatus
from app.core.exceptions import PipelineError, RecordNotFoundError, SourceNotFoundError
from app.features.submissions.access import viewer_can_see
from app.features.submissions.repository import SubmissionRepository
from app.features.verification.schemas import (
    VerificationQueuedResponse,
    VerificationRequest,
    VerificationResponse,
    VerificationStatusResponse,
)
from app.features.verification.service import VerificationService
from app.features.auth.security import get_current_user_optional
from app.features.auth.models import User
from app.shared.dependencies import get_submission_repo, get_verification_service

router = APIRouter(prefix="/verify", tags=["Verification"])


@router.post(
    "",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a news claim against its claimed source",
    description=(
        "Submit a news headline and claimed source (optionally a body and a "
        "claimed date). The system finds the corresponding source report and "
        "returns independent findings: source_status (CONFIRMED | NOT_FOUND | "
        "INCOMPLETE); the Headline Alteration verdict content_status (MATCHED | "
        "ALTERED, headline vs source title only, null with headline_check_status "
        "explaining why when no verdict was reached); date_status; and, when a "
        "body was submitted, four body similarity scores (measurements only, "
        "never a verdict) in analysis.body_similarity."
    ),
    responses={
        200: {"description": "Verification result (may be cached)"},
        404: {"description": "Claimed source could not be resolved to a registered news source"},
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
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "source_not_found",
                "message": exc.message,
                "claimed_source": exc.claimed_source,
            },
        ) from exc
    except PipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "pipeline_failure",
                "message": exc.message,
                "details": exc.details,
            },
        ) from exc


@router.post(
    "/async",
    response_model=VerificationQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue a claim for verification and return immediately",
    description=(
        "Registers the claim and runs the 12-stage pipeline in the background. "
        "Responds at once with a submission ID to poll via "
        "`GET /verify/{submission_id}/status`, so the caller does not have to "
        "wait on the request. If this exact claim was verified before, the "
        "existing submission is returned with `cached: true` and nothing is "
        "re-run."
    ),
    responses={
        202: {"description": "Claim accepted (or an existing result reused)"},
        404: {"description": "Claimed source could not be resolved to a registered news source"},
        422: {"description": "Invalid request payload"},
    },
)
async def verify_claim_async(
    request: VerificationRequest,
    http_request: Request,
    service: VerificationService = Depends(get_verification_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> VerificationQueuedResponse:
    submitter_id = current_user.id if current_user else None
    try:
        submission_id, submission_status, cached = await service.register_claim(
            request, submitter_id=submitter_id
        )
    except SourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "source_not_found",
                "message": exc.message,
                "claimed_source": exc.claimed_source,
            },
        ) from exc

    if not cached:
        # The job row was committed with the submission; this only wakes the
        # worker so it starts without waiting for its next poll.
        worker = getattr(http_request.app.state, "job_worker", None)
        if worker is not None:
            worker.wake()

    return VerificationQueuedResponse(
        submission_id=submission_id,
        status=submission_status,
        cached=cached,
    )


@router.get(
    "/{submission_id}",
    response_model=VerificationResponse,
    summary="Get a verification result by submission ID",
    responses={
        200: {"description": "Verification result"},
        404: {"description": "Submission not found or not yet completed"},
    },
)
async def get_verification_result(
    submission_id: uuid.UUID,
    service: VerificationService = Depends(get_verification_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> VerificationResponse:
    submission = await service.submission_repo.get_by_id_or_none(submission_id)
    result = await service.get_result(submission_id)
    if result is None or submission is None or not viewer_can_see(submission, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )
    return result


@router.get(
    "/{submission_id}/status",
    response_model=VerificationStatusResponse,
    summary="Poll the status of a verification request",
    responses={
        200: {"description": "Current pipeline status"},
        404: {"description": "Submission not found"},
    },
)
async def get_verification_status(
    submission_id: uuid.UUID,
    submission_repo: SubmissionRepository = Depends(get_submission_repo),
    service: VerificationService = Depends(get_verification_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> VerificationStatusResponse:
    try:
        submission = await submission_repo.get_by_id(submission_id)
    except RecordNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )
    if not viewer_can_see(submission, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )

    result = None
    if submission.status in (
        SubmissionStatus.EXPERT_REVIEW,
        SubmissionStatus.FINALIZED,
        SubmissionStatus.ESCALATED,
    ):
        result = await service.get_result(submission_id)

    return VerificationStatusResponse(
        submission_id=submission_id,
        status=submission.status,
        phase=submission.processing_phase,
        result=result,
        error=submission.failure_reason if submission.status == SubmissionStatus.FAILED else None,
        queued_at=submission.created_at,
        updated_at=submission.updated_at,
    )
