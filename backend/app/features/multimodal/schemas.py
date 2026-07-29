from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MultimodalPredictionResponse(BaseModel):

    prediction_id: str = Field(..., description="UUID of the stored prediction record")
    prediction: str = Field(..., description="'FAKE' or 'NON_FAKE'")
    confidence_fake: float = Field(
        ..., ge=0.0, le=1.0, description="P(FAKE) from softmax"
    )
    confidence_real: float = Field(
        ..., ge=0.0, le=1.0, description="P(NON_FAKE) from softmax"
    )
    is_cached: bool = Field(..., description="True if a previous prediction was reused")
    original_id: Optional[str] = Field(
        default=None,
        description="UUID of the original prediction this was deduplicated from",
    )
    similarity_scores: Optional[dict[str, float]] = Field(
        default=None,
        description="Cosine similarity scores (text/image/combined) when is_cached=True",
    )
    minio_object_key: str = Field(
        ..., description="MinIO object key of the stored image"
    )
    model_version: str = Field(..., description="Model version tag")
    created_at: datetime = Field(
        ..., description="Prediction record creation timestamp"
    )


class MultimodalPredictionDetail(BaseModel):

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

    items: list[MultimodalPredictionDetail]
    total: int
    limit: int
    offset: int
