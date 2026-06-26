"""
app/features/multimodal/models.py
====================================
ORM model for the multimodal (BanglaBERT + EfficientNet-B4) fake-news
preliminary prediction feature.

Design decisions:
- Embeddings are stored as PostgreSQL ARRAY(Float) columns so that Python-side
  cosine similarity search can be performed without requiring pgvector.
  A future migration can add a pgvector column for ANN indexing at scale.
- `is_duplicate_of_id` links a reused result back to the original prediction
  that produced the actual inference, giving a full audit trail.
- `model_version` allows the deduplication logic to refuse to reuse predictions
  produced by an older model version when the model is upgraded.
- headline and body_text are stored separately (as submitted), while the
  model only sees body_text for inference.

Tables:
    multimodal_predictions  - one row per unique (body_text, image) submission
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ARRAY, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDMixin


class MultimodalPrediction(UUIDMixin, TimestampMixin, Base):
    """
    Stores the result of a multimodal fake-news prediction request.

    Columns:
        headline           — Raw user-submitted headline (stored for display only).
        body_text          — Article body text; used as the text input to the model.
        minio_object_key   — MinIO object key for the uploaded image (e.g.
                             ``multimodal/{uuid}/{filename}``).
        prediction         — Model output label: ``"FAKE"`` or ``"NON_FAKE"``.
        confidence_fake    — Softmax probability for the FAKE class (0–1).
        confidence_real    — Softmax probability for the REAL class (0–1).
        text_embedding     — BanglaBERT [CLS] token vector (768-dim) used for
                             duplicate detection.
        image_embedding    — EfficientNet-B4 global-pool features (1792-dim) used
                             for duplicate detection.
        combined_embedding — L2-normalised concatenation of text + image embeddings
                             (2560-dim); primary similarity search key.
        model_version      — Model version tag for upgrade traceability.
        is_duplicate_of_id — UUID of the original prediction that this result
                             was reused from; NULL for freshly inferred results.
    """

    __tablename__ = "multimodal_predictions"

    # ── Submitted content ─────────────────────────────────────────────────
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

    # ── Storage reference ─────────────────────────────────────────────────
    minio_object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="MinIO object key for the uploaded image (multimodal/{uuid}/{filename})",
    )

    # ── Prediction result ─────────────────────────────────────────────────
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

    # ── Multimodal embeddings (duplicate detection) ───────────────────────
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

    # ── Model provenance ──────────────────────────────────────────────────
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="banglabert_efficientnetb4_v1",
        comment="Model version tag — deduplication only reuses predictions of the same version",
    )

    # ── Deduplication reference ───────────────────────────────────────────
    is_duplicate_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("multimodal_predictions.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        comment="Original prediction UUID if this row was a cache hit; NULL for fresh inference",
    )

    __table_args__ = (
        # Index on created_at for efficient recent-N queries during dedup search
        Index("ix_multimodal_predictions_created_at", "created_at"),
        # Index on model_version to filter dedup candidates by version
        Index("ix_multimodal_predictions_model_version", "model_version"),
    )
