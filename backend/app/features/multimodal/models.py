
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ARRAY, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDMixin


class MultimodalPrediction(UUIDMixin, TimestampMixin, Base):

    __tablename__ = "multimodal_predictions"


    headline: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User-submitted news headline (stored for display, not used by model)",
    )
    body_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Article body text — the sole text input to the BanglaBERT backbone",
    )


    minio_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="MinIO object key for the uploaded image (multimodal/{uuid}/{filename})",
    )


    prediction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Model output label: FAKE or NON_FAKE",
    )
    confidence_fake: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Softmax probability for the FAKE class (0.0–1.0)",
    )
    confidence_real: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Softmax probability for the NON_FAKE class (0.0–1.0)",
    )


    text_embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        comment="BanglaBERT [CLS] embedding vector (768-dim) for text similarity",
    )
    image_embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        comment="EfficientNet-B4 global-pool features (1792-dim) for image similarity",
    )
    combined_embedding: Mapped[list[float]] = mapped_column(
        ARRAY(Float),
        nullable=False,
        comment="L2-normalised concat of text+image embeddings (2560-dim); primary dedup key",
    )


    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="banglabert_efficientnetb4_v1",
        comment="Model version tag — deduplication only reuses predictions of the same version",
    )


    is_duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multimodal_predictions.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="Original prediction UUID if this row was a cache hit; NULL for fresh inference",
    )

    __table_args__ = (

        Index("ix_multimodal_predictions_created_at", "created_at"),

        Index("ix_multimodal_predictions_model_version", "model_version"),
    )
