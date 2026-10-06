from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RecordNotFoundError
from app.features.auth.models import User
from app.features.auth.security import get_current_user_optional
from app.features.expert_review.public_votes import PublicVotingDetails, load_public_voting_details
from app.features.submissions.access import viewer_can_see
from app.features.submissions.repository import SubmissionRepository
from app.features.submissions.schemas import SubmissionLookupResponse
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.get(
    "/{submission_id}",
    response_model=SubmissionLookupResponse,
    summary="Look up a submission's type and basic metadata",
    description=(
        "Returns just enough to know which detail endpoint to call next: "
        "submission_type tells the caller whether to fetch "
        "GET /verify/{id} (SOURCE_BASED), GET /multimodal/by-submission/{id} "
        "(MULTIMODAL), or GET /photocard/{id} (PHOTO_CARD)."
    ),
    responses={404: {"description": "Submission not found"}},
)
async def get_submission(
    submission_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User | None = Depends(get_current_user_optional),
) -> SubmissionLookupResponse:
    from app.features.verification.presenter import effective_status

    repo = SubmissionRepository(session)
    try:
        submission = await repo.get_by_id(submission_id)
    except RecordNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )
    # Pending/failed submissions are the submitter's private working state.
    if not viewer_can_see(submission, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )

    original_status = None
    if submission.duplicate_of_submission_id:
        original = await repo.get_by_id_or_none(submission.duplicate_of_submission_id)
        original_status = original.status if original else None

    return SubmissionLookupResponse(
        submission_id=submission.id,
        submission_type=submission.submission_type,
        status=effective_status(submission, original_status),
        processing_phase=submission.processing_phase,
        failure_reason=submission.failure_reason,
        headline=submission.headline,
        body_text=submission.body_text,
        claimed_source_text=submission.claimed_source_text,
        published_date=submission.published_date,
        created_at=submission.created_at,
    )


@router.get(
    "/{submission_id}/voting-details",
    response_model=PublicVotingDetails,
    summary="Public reviewer votes and justifications (after the final decision only)",
    description=(
        "Each reviewer's overall vote and justification for this claim, with an "
        "administrator's final decision on an escalated claim clearly marked. "
        "Public, including for signed-out visitors, but only once the claim has a "
        "final decision; before that this returns 404 so no in-progress review "
        "is disclosed."
    ),
    responses={404: {"description": "Not found, or no final decision yet"}},
)
async def get_voting_details(
    submission_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> PublicVotingDetails:
    submission = await SubmissionRepository(session).get_by_id_or_none(submission_id)
    details = await load_public_voting_details(session, submission) if submission else None
    if details is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "voting_details_unavailable", "submission_id": str(submission_id)},
        )
    return details
