from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ARRAY, CheckConstraint, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import MultimodalPredictionLabel, OverallVerdict
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.submissions.models import Submission


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

    expert_overall_verdict: Mapped[OverallVerdict | None] = mapped_column(
        Enum(OverallVerdict, name="overall_verdict_enum", create_type=False),
        nullable=True,
        comment=(
            "Expert-finalized Overall verdict — NULL until expert review "
            "finalizes this claim. Not written by the inference engine."
        ),
    )

    finalized_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When expert review finalized this claim; NULL until then.",
    )

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
