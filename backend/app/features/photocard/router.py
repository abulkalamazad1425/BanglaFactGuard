from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.core.config import get_settings
from app.core.exceptions import (
    BanglaFactGuardError,
    ImageStorageUnavailableError,
    PhotoCardExtractionFailedError,
    PipelineError,
    SourceNotFoundError,
)
from app.features.auth.models import User
from app.features.auth.security import get_current_user_optional
from app.features.photocard.dependencies import get_photocard_service
from app.features.photocard.ocr_service import (
    OcrEngineUnavailableError,
    OcrFailedError,
)
from app.features.photocard.schemas import (
    PhotoCardAcceptedResponse,
    PhotoCardResultResponse,
    PhotoCardVerifyResponse,
)
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
    max_bytes = _SETTINGS.ocr.max_image_bytes
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
    summary="Accept a photo card for background verification",
    description=(
        "Validates the inputs, durably stores the image and records a "
        "PHOTO_CARD submission (linked to the signed-in submitter, if any) "
        "with its job - then returns HTTP 202 at once. OCR, headline "
        "extraction (Gemini, with the existing deterministic extractor as "
        "fallback) and the shared 12-stage verification run on the server "
        "whether or not the browser stays open. Poll "
        "`GET /photocard/{submission_id}` (or open it later from My "
        "Submissions) for the current state and, when complete, the saved "
        "result. The card is always verified headline-only against the "
        "claimed source and published date given here."
    ),
    responses={
        202: {"description": "Card accepted; processing continues in the background"},
        404: {"description": "Claimed source could not be resolved to a registered news source"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
        503: {"description": "Image storage unavailable - nothing was accepted"},
    },
)
async def verify_photocard_async(
    http_request: Request,
    image: UploadFile = File(..., description="Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)"),
    claimed_source_text: str = Form(..., min_length=1, max_length=255),
    published_date: date | None = Form(default=None),
    force_refresh: bool = Form(default=False),
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardAcceptedResponse:
    image_bytes = await _read_validated_image(image)
    claimed_source_text = claimed_source_text.strip()
    if not claimed_source_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="claimed_source_text must not be blank.",
        )
    try:
        submission = await service.accept_upload(
            image_bytes=image_bytes,
            original_filename=image.filename or "photocard.jpg",
            claimed_source_text=claimed_source_text,
            published_date=published_date,
            force_refresh=force_refresh,
            submitter_id=current_user.id if current_user else None,
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
    except ImageStorageUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "image_storage_unavailable", "message": exc.message},
        ) from exc

    worker = getattr(http_request.app.state, "job_worker", None)
    if worker is not None:
        worker.wake()  # the job is already durable; this only cuts latency
    return service.accepted_response(submission)


@router.post(
    "/verify",
    response_model=PhotoCardVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify a photo card — unattended, single pass",
    description=(
        "Upload a Bangla news photo card or screenshot together with the "
        "claimed source and (optionally) the published date it claims. The "
        "system runs OCR, extracts a single headline (Gemini first, falling "
        "back to a deterministic extractor on any failure or ungrounded "
        "output), and verifies that headline against the claimed source "
        "through the same 12-stage pipeline used by `POST /verify` for "
        "typed claims — evidence search restricted to the claimed source, "
        "article extraction, multi-dimensional similarity, contradiction "
        "detection, and manipulation checks — returning a 3-dimensional "
        "verdict: source_status, content_status, date_status.\n\n"
        "There is no confirmation step: extraction and verification happen "
        "in one unattended pass. The card is always verified against its "
        "headline alone (no body/caption). If the card's own text implies "
        "a different source or date than provided, that conflict is "
        "recorded and surfaced (`source_date_conflict`) but never silently "
        "overrides the claimed_source_text/published_date given here — "
        "those are the verification targets.\n\n"
        "If the resulting claim matches one already verified, the earlier "
        "result is reused and flagged with `reused_previous_result`. Open "
        "to all users, signed in or not."
    ),
    responses={
        200: {"description": "Verification result"},
        404: {"description": "Claimed source could not be resolved to a registered news source"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
        422: {"description": "No readable headline could be extracted from the image"},
        500: {"description": "Pipeline failure — critical stage error"},
        503: {"description": "No Bangla OCR engine is installed"},
    },
)
async def verify_photocard(
    image: UploadFile = File(
        ..., description="Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)"
    ),
    claimed_source_text: str = Form(
        ..., min_length=1, max_length=255,
        description="The source/outlet this card claims to be from — the verification target.",
    ),
    published_date: date | None = Form(
        default=None, description="The date this card claims to have been published, if known."
    ),
    force_refresh: bool = Form(default=False),
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardVerifyResponse:
    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported image type: {image.content_type!r}. "
                f"Allowed types: {sorted(_ALLOWED_CONTENT_TYPES)}"
            ),
        )

    claimed_source_text = claimed_source_text.strip()
    if not claimed_source_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="claimed_source_text must not be blank.",
        )

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )
    max_bytes = _SETTINGS.ocr.max_image_bytes
    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the maximum size of {max_bytes // (1024 * 1024)} MB.",
        )

    try:
        return await service.verify(
            image_bytes=image_bytes,
            original_filename=image.filename or "photocard.jpg",
            claimed_source_text=claimed_source_text,
            published_date=published_date,
            force_refresh=force_refresh,
            submitter_id=current_user.id if current_user else None,
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
    except (OcrEngineUnavailableError, OcrFailedError) as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail={"error": "ocr_failed", "message": exc.message, **exc.details},
        ) from exc
    except PhotoCardExtractionFailedError as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail={
                "error": "extraction_failed",
                "message": exc.message,
                **exc.details,
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
    except BanglaFactGuardError as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail={"error": "photocard_verify_failed", "message": exc.message},
        ) from exc


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
