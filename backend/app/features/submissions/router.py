from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RecordNotFoundError
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
) -> SubmissionLookupResponse:
    repo = SubmissionRepository(session)
    try:
        submission = await repo.get_by_id(submission_id)
    except RecordNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )

    return SubmissionLookupResponse(
        submission_id=submission.id,
        submission_type=submission.submission_type,
        status=submission.status,
        headline=submission.headline,
        claimed_source_text=submission.claimed_source_text,
        published_date=submission.published_date,
        created_at=submission.created_at,
    )
