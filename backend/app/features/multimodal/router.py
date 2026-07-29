
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    BanglaFactGuardError,
    ModelNotLoadedError,
    RecordNotFoundError,
)
from app.db.engine import get_async_session
from app.features.multimodal.schemas import (
    MultimodalPredictionDetail,
    MultimodalPredictionResponse,
    PredictionListResponse,
)
from app.features.multimodal.service import MultimodalPredictionService
from app.features.multimodal.storage_service import MultimodalStorageService

logger = structlog.get_logger(__name__)
_SETTINGS = get_settings()

router = APIRouter(prefix="/multimodal", tags=["Multimodal Fake-News Detection"])





_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
}






def _get_loader(request: Request):
    loader = getattr(request.app.state, "multimodal_loader", None)
    if loader is None or not loader.is_loaded:
        raise ModelNotLoadedError("MultimodalModelLoader")
    return loader


def _get_storage(request: Request) -> MultimodalStorageService:
    storage = getattr(request.app.state, "multimodal_storage", None)
    if storage is None:
        raise ModelNotLoadedError("MultimodalStorageService")
    return storage







@router.post(
    "/predict",
    response_model=MultimodalPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Multimodal Fake-News Preliminary Prediction",
    description=(
        "Submit a news article (headline, body text, and image) for preliminary "
        "fake-news detection using the BanglaBERT + EfficientNet-B4 multimodal model. "
        "\n\n"
        "**Duplicate detection**: If an identical or near-identical submission has "
        "been processed before, the cached prediction is returned without re-running "
        "inference. Similarity is evaluated independently on text semantics, image "
        "content, and a combined multimodal fingerprint — all three must exceed "
        "their respective thresholds for a cache hit to occur."
        "\n\n"
        "**Input**: ``multipart/form-data`` with fields ``headline``, ``body_text``, "
        "and ``image`` (JPEG/PNG/WebP, max 10 MB)."
    ),
    response_description="Prediction result with confidence scores and deduplication metadata",
)
async def predict(
    request: Request,
    headline: str = Form(
        ...,
        min_length=1,
        max_length=2000,
        description="News headline (stored for display; not used by the model)",
    ),
    body_text: str = Form(
        ...,
        min_length=10,
        max_length=50_000,
        description="Article body text — the text input to the BanglaBERT backbone",
    ),
    image: UploadFile = File(
        ...,
        description="News article image (JPEG/PNG/WebP, max 10 MB)",
    ),
    db: AsyncSession = Depends(get_async_session),
) -> MultimodalPredictionResponse:

    if image.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported image type: {image.content_type!r}. "
                f"Allowed types: {sorted(_ALLOWED_CONTENT_TYPES)}"
            ),
        )

    image_bytes = await image.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds maximum size of {_MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty.",
        )

    loader = _get_loader(request)
    storage = _get_storage(request)

    service = MultimodalPredictionService(db=db, loader=loader, storage=storage)

    try:
        response = await service.predict(
            headline=headline,
            body_text=body_text,
            image_bytes=image_bytes,
            original_filename=image.filename or "upload.jpg",
        )
    except ModelNotLoadedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.message,
        ) from exc
    except BanglaFactGuardError as exc:
        raise HTTPException(
            status_code=exc.http_status_code,
            detail=exc.message,
        ) from exc

    return response


@router.get(
    "/predict/{prediction_id}",
    response_model=MultimodalPredictionDetail,
    summary="Get Prediction by ID",
    description="Retrieve a stored multimodal prediction record by its UUID.",
)
async def get_prediction(
    prediction_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_async_session),
) -> MultimodalPredictionDetail:
    loader = _get_loader(request)
    storage = _get_storage(request)
    service = MultimodalPredictionService(db=db, loader=loader, storage=storage)

    try:
        record = await service.get_prediction(prediction_id)
    except RecordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc

    return MultimodalPredictionDetail(
        prediction_id=str(record.id),
        headline=record.headline,
        body_text=record.body_text,
        prediction=record.prediction,
        confidence_fake=record.confidence_fake,
        confidence_real=record.confidence_real,
        is_cached=record.is_duplicate_of_id is not None,
        original_id=str(record.is_duplicate_of_id) if record.is_duplicate_of_id else None,
        minio_object_key=record.minio_object_key,
        model_version=record.model_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/predictions",
    response_model=PredictionListResponse,
    summary="List Recent Predictions",
    description="Return a paginated list of recent multimodal predictions ordered by creation time (newest first).",
)
async def list_predictions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_session),
) -> PredictionListResponse:
    loader = _get_loader(request)
    storage = _get_storage(request)
    service = MultimodalPredictionService(db=db, loader=loader, storage=storage)

    records, total = await service.list_predictions(limit=limit, offset=offset)

    items = [
        MultimodalPredictionDetail(
            prediction_id=str(r.id),
            headline=r.headline,
            body_text=r.body_text,
            prediction=r.prediction,
            confidence_fake=r.confidence_fake,
            confidence_real=r.confidence_real,
            is_cached=r.is_duplicate_of_id is not None,
            original_id=str(r.is_duplicate_of_id) if r.is_duplicate_of_id else None,
            minio_object_key=r.minio_object_key,
            model_version=r.model_version,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in records
    ]

    return PredictionListResponse(items=items, total=total, limit=limit, offset=offset)
