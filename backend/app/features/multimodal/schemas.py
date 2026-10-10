from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.constants import OverallVerdict


class MultimodalPredictionResponse(BaseModel):

    prediction_id: str = Field(..., description="UUID of the stored prediction record")
    submission_id: str = Field(..., description="UUID of the paired submissions row")
    prediction: str = Field(..., description="'FAKE' or 'NON_FAKE' — the AI's preliminary call")
    confidence_fake: float = Field(
        ..., ge=0.0, le=1.0, description="P(FAKE) from softmax"
    )
    confidence_real: float = Field(
        ..., ge=0.0, le=1.0, description="P(NON_FAKE) from softmax"
    )
    expert_overall_verdict: Optional[OverallVerdict] = Field(
        default=None,
        description=(
            "Expert-finalized Overall verdict (Fake/Real/Misleading/Altered). "
            "NULL until expert review completes — the prediction above is "
            "only the AI's preliminary call."
        ),
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
    image_url: Optional[str] = Field(
        default=None,
        description="Pre-signed, time-limited URL for displaying the uploaded image",
    )
    model_version: str = Field(..., description="Model version tag")
    created_at: datetime = Field(
        ..., description="Prediction record creation timestamp"
    )


class MultimodalPredictionDetail(BaseModel):

    prediction_id: str
    submission_id: str
    headline: str | None
    body_text: str | None
    prediction: str
    confidence_fake: float
    confidence_real: float
    expert_overall_verdict: Optional[OverallVerdict] = None
    is_cached: bool
    original_id: Optional[str] = None
    original_submission_id: Optional[str] = Field(
        default=None,
        description=(
            "Set when this upload matched an earlier claim: that claim's "
            "submission id. Its review outcome is the one shown here."
        ),
    )
    minio_object_key: str
    image_url: Optional[str] = Field(
        default=None,
        description="Pre-signed, time-limited URL for displaying the uploaded image",
    )
    model_version: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PredictionListResponse(BaseModel):

    items: list[MultimodalPredictionDetail]
    total: int
    limit: int
    offset: int
