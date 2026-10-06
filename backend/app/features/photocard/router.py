from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from app.core.config import get_settings
from app.core.exceptions import ImageStorageUnavailableError
from app.features.auth.models import User
from app.features.auth.security import get_current_user_optional
from app.features.photocard.dependencies import get_photocard_service
from app.features.photocard.schemas import PhotoCardAcceptedResponse, PhotoCardResultResponse
from app.features.photocard.service import PhotoCardService
from app.features.submissions.access import viewer_can_see

router = APIRouter(prefix="/photocard", tags=["Photo Card Verification"])

_SETTINGS = get_settings()

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


async def _read_validated_image(image: UploadFile) -> bytes:
    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported image type: {image.content_type!r}. "
                f"Allowed types: {sorted(_ALLOWED_CONTENT_TYPES)}"
            ),
        )
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image file is empty."
        )
    max_bytes = _SETTINGS.photocard.max_image_bytes
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the maximum size of {max_bytes // (1024 * 1024)} MB.",
        )
    return image_bytes


@router.post(
    "/verify/async",
    response_model=PhotoCardAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Accept a photo card image for background verification",
    description=(
        "Only the image is submitted. It is durably stored and a PHOTO_CARD "
        "submission (linked to the signed-in submitter, if any) is recorded "
        "with its job - then HTTP 202 is returned at once. On the server Gemini "
        "reads the headline, identifies the claimed news outlet among the active "
        "verified sources (using their known aliases) and reads the printed "
        "publication date (at most 9 requests: 3 batches of 3, 10 s apart). "
        "Those values become the claim's headline, claimed outlet and claimed "
        "date, and the headline goes through the shared verification pipeline. "
        "If Gemini cannot be reached, or the card shows no headline or no "
        "recognised verified outlet, the submission FAILS with a reason and no "
        "verification runs. Poll `GET /photocard/{submission_id}` (or open it "
        "later from My Submissions) for the current state and the saved result."
    ),
    responses={
        202: {"description": "Card accepted; processing continues in the background"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
        503: {"description": "Image storage unavailable - nothing was accepted"},
    },
)
async def verify_photocard_async(
    http_request: Request,
    image: UploadFile = File(..., description="Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)"),
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardAcceptedResponse:
    image_bytes = await _read_validated_image(image)
    try:
        submission = await service.accept_upload(
            image_bytes=image_bytes,
            original_filename=image.filename or "photocard.jpg",
            submitter_id=current_user.id if current_user else None,
        )
    except ImageStorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "image_storage_unavailable", "message": exc.message},
        ) from exc

    worker = getattr(http_request.app.state, "job_worker", None)
    if worker is not None:
        worker.wake()  # the job is already durable; this only cuts latency
    return service.accepted_response(submission)


@router.get(
    "/{submission_id}",
    response_model=PhotoCardResultResponse,
    summary="Get a stored photo-card report",
    responses={
        200: {"description": "Photo-card report"},
        404: {"description": "Submission not found"},
    },
)
async def get_photocard_result(
    submission_id: uuid.UUID,
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardResultResponse:
    result = await service.get_result(submission_id)
    submission = await service.submission_repo.get_by_id_or_none(submission_id)
    # A pending/failed card is its submitter's private working state.
    if result is None or submission is None or not viewer_can_see(submission, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )
    return result
