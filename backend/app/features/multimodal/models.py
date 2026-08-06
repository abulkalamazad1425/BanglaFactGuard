from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ARRAY, CheckConstraint, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MultimodalPredictionLabel
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.submissions.models import Submission


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


class MultimodalAnalysis(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.9 — multimodal_analysis.

    Live storage target for the `/multimodal/predict` endpoint (replacing
    `MultimodalPrediction` above, which is now frozen/legacy), tied 1:1 to a
    `Submission` row per the thesis ER diagram.
    """

    __tablename__ = "multimodal_analysis"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    image_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    prediction: Mapped[MultimodalPredictionLabel] = mapped_column(
        Enum(
            MultimodalPredictionLabel,
            name="multimodal_prediction_enum",
            create_type=True,
        ),
        nullable=False,
    )

    confidence_fake: Mapped[float] = mapped_column(Float, nullable=False)

    confidence_real: Mapped[float] = mapped_column(Float, nullable=False)

    text_embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
        comment="BanglaBERT [CLS] embedding vector (768-dim)",
    )
    image_embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
        comment="EfficientNet-B4 global-pool features (1792-dim)",
    )
    combined_embedding: Mapped[list[float] | None] = mapped_column(
        ARRAY(Float),
        nullable=True,
        comment="L2-normalised concat of text+image embeddings (2560-dim)",
    )

    model_version: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )

    is_duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multimodal_analysis.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment=(
            "Not in DatabaseDescription.pdf Table 4.9 — added because the PDF's "
            "multimodal_analysis has no dedup column and the live duplicate-"
            "detection feature needs one. Mirrors legacy "
            "multimodal_predictions.is_duplicate_of_id."
        ),
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="MultimodalAnalysis.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "confidence_fake >= 0.0 AND confidence_fake <= 1.0",
            name="ck_multimodal_analysis_confidence_fake_range",
        ),
        CheckConstraint(
            "confidence_real >= 0.0 AND confidence_real <= 1.0",
            name="ck_multimodal_analysis_confidence_real_range",
        ),
    )
