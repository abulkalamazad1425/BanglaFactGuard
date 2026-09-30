from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.exceptions import (
    BanglaFactGuardError,
    PipelineError,
    PermissionDeniedError,
)
from app.features.auth.models import User
from app.features.auth.security import get_current_user_optional
from app.features.photocard.dependencies import get_photocard_service
from app.features.photocard.ocr_service import (
    OcrEngineUnavailableError,
    OcrFailedError,
)
from app.features.photocard.schemas import (
    PhotoCardExtractResponse,
    PhotoCardResultResponse,
    PhotoCardVerifyRequest,
    PhotoCardVerifyResponse,
)
from app.features.photocard.service import PhotoCardService

router = APIRouter(prefix="/photocard", tags=["Photo Card Verification"])

_SETTINGS = get_settings()

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


@router.post(
    "/extract",
    response_model=PhotoCardExtractResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 1 — read a photo card and draft the claim",
    description=(
        "Upload a Bangla news photo card or screenshot. The system runs OCR, "
        "strips card chrome (social handles, follow/share prompts, bylines, "
        "photo credits, timestamps, watermarks) and non-Bangla lines, splits "
        "what remains into a headline and body, and detects which **active "
        "verified source** the card is branded with.\n\n"
        "Nothing is verified here. The response carries a `draft_id` plus the "
        "suggested text, which the user reviews and corrects before calling "
        "`POST /photocard/verify`.\n\n"
        "Open to all users, signed in or not."
    ),
    responses={
        200: {"description": "Extracted claim awaiting user confirmation"},
        413: {"description": "Image too large"},
        415: {"description": "Unsupported image type"},
        422: {"description": "No readable text in the image"},
        503: {"description": "No Bangla OCR engine is installed"},
    },
)
async def extract_photocard(
    image: UploadFile = File(
        ..., description="Photo card or screenshot (JPEG/PNG/WebP/GIF, max 10 MB)"
    ),
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardExtractResponse:
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
        return await service.extract(
            image_bytes=image_bytes,
            original_filename=image.filename or "photocard.jpg",
            submitter_id=current_user.id if current_user else None,
        )
    except (OcrEngineUnavailableError, OcrFailedError) as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail={"error": "ocr_failed", "message": exc.message, **exc.details},
        ) from exc
    except BanglaFactGuardError as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail={"error": "photocard_extract_failed", "message": exc.message},
        ) from exc


@router.post(
    "/verify",
    response_model=PhotoCardVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 2 — verify the confirmed claim against its claimed source",
    description=(
        "Submit the OCR text the user confirmed, together with the claimed "
        "source. The claim runs through the same source-based verification "
        "pipeline used by `POST /verify` — evidence search restricted to the "
        "claimed source, article extraction, multi-dimensional similarity, "
        "contradiction detection and manipulation checks — and returns "
        "TRUE | FALSE | PARTIALLY_TRUE | NOT_FOUND_IN_CLAIMED_SOURCE.\n\n"
        "If the confirmed claim matches one already verified, the earlier "
        "result is reused and flagged with `reused_previous_result`."
    ),
    responses={
        200: {"description": "Verification result"},
        403: {"description": "Draft belongs to another account"},
        404: {"description": "Draft not found"},
        409: {"description": "Draft already verified"},
        500: {"description": "Pipeline failure — critical stage error"},
    },
)
async def verify_photocard(
    request: PhotoCardVerifyRequest,
    service: PhotoCardService = Depends(get_photocard_service),
    current_user: User | None = Depends(get_current_user_optional),
) -> PhotoCardVerifyResponse:
    try:
        return await service.verify(
            request, submitter_id=current_user.id if current_user else None
        )
    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": exc.message},
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
) -> PhotoCardResultResponse:
    result = await service.get_result(submission_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "submission_id": str(submission_id)},
        )
    return result
