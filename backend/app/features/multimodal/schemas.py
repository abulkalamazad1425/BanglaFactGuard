"""
app/features/multimodal/schemas.py
====================================
Pydantic v2 request/response schemas for the multimodal prediction API.

Design decisions:
- Request is a multipart/form-data body (headline + body_text fields + image file).
  FastAPI handles this via ``Form(...)`` + ``UploadFile``.
- Response is a rich JSON object including prediction, confidence scores,
  deduplication metadata, and a reference to the MinIO-stored image.
- ``MultimodalPredictionDetail`` is the full DB-record representation used
  for the GET /predict/{id} endpoint.
- All UUID fields are serialized as strings for JSON transport.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MultimodalPredictionResponse(BaseModel):
    """
    Response returned by ``POST /api/v1/multimodal/predict``.

    Fields:
        prediction_id:      UUID of the stored prediction record.
        prediction:         ``"FAKE"`` or ``"NON_FAKE"``.
        confidence_fake:    Softmax probability for the FAKE class (0.0–1.0).
        confidence_real:    Softmax probability for the NON_FAKE class (0.0–1.0).
        is_cached:          True if an existing prediction was reused (no new inference).
        original_id:        If ``is_cached=True``, the UUID of the prediction that was reused.
        similarity_scores:  Cosine similarity scores for each modality (only present when
                            ``is_cached=True``, for transparency).
        minio_object_key:   Key under which the image was stored in MinIO.
        model_version:      Model version that produced this prediction.
        created_at:         Timestamp when the prediction record was created.
    """

    prediction_id: str = Field(..., description="UUID of the stored prediction record")
    prediction: str = Field(..., description="'FAKE' or 'NON_FAKE'")
    confidence_fake: float = Field(..., ge=0.0, le=1.0, description="P(FAKE) from softmax")
    confidence_real: float = Field(..., ge=0.0, le=1.0, description="P(NON_FAKE) from softmax")
    is_cached: bool = Field(..., description="True if a previous prediction was reused")
    original_id: Optional[str] = Field(
        default=None,
        description="UUID of the original prediction this was deduplicated from",
    )
    similarity_scores: Optional[dict[str, float]] = Field(
        default=None,
        description="Cosine similarity scores (text/image/combined) when is_cached=True",
    )
    minio_object_key: str = Field(..., description="MinIO object key of the stored image")
    model_version: str = Field(..., description="Model version tag")
    created_at: datetime = Field(..., description="Prediction record creation timestamp")


class MultimodalPredictionDetail(BaseModel):
    """
    Full prediction record returned by ``GET /api/v1/multimodal/predict/{id}``.

    Includes all fields from ``MultimodalPredictionResponse`` plus the stored
    headline and body_text.
    """

    prediction_id: str
    headline: str
    body_text: str
    prediction: str
    confidence_fake: float
    confidence_real: float
    is_cached: bool
    original_id: Optional[str] = None
    minio_object_key: str
    model_version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PredictionListResponse(BaseModel):
    """Paginated list of recent predictions."""

    items: list[MultimodalPredictionDetail]
    total: int
    limit: int
    offset: int
