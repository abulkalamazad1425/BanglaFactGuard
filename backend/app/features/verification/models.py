"""
app/features/verification/models.py
=====================================
ORM models for the verification feature.

Consolidated from:
  - app/models/verified_claim.py
  - app/models/verification_result.py
  - app/models/verification_log.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ClaimStatus,
    LogLevel,
    PipelineStageID,
    VerificationLabel,
)
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.articles.models import RetrievedArticle, SearchQuery
    from app.features.sources.models import SourceRegistry


# ---------------------------------------------------------------------------
# VerifiedClaim
# ---------------------------------------------------------------------------


class VerifiedClaim(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Records a single fact-checking request and its lifecycle state.

    The `claim_hash` column is the deduplication key: before running the
    full pipeline, the system checks whether a result for this hash already
    exists (Stage 2 DB cache lookup).
    """

    __tablename__ = "verified_claims"

    claim_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="SHA-256 hex of normalised (headline + claimed_source) — dedup key",
    )

    headline: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw headline as submitted in the verification request",
    )

    news_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Raw article body as submitted (may be empty for headline-only claims)",
    )

    claimed_source: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Raw source string as provided by the user",
    )

    normalized_source: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Resolved canonical domain (e.g. prothomalo.com)",
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_registry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to source_registry.id — set when source is successfully resolved",
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Alleged publication date supplied in the request (optional)",
    )

    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status_enum", create_type=True),
        nullable=False,
        default=ClaimStatus.PENDING,
        index=True,
        comment="Pipeline lifecycle state: pending → processing → completed/failed",
    )

    source: Mapped["SourceRegistry | None"] = relationship(
        "SourceRegistry",
        back_populates="claims",
        lazy="select",
    )

    search_queries: Mapped[list["SearchQuery"]] = relationship(
        "SearchQuery",
        back_populates="claim",
        lazy="select",
        cascade="all, delete-orphan",
    )

    retrieved_articles: Mapped[list["RetrievedArticle"]] = relationship(
        "RetrievedArticle",
        back_populates="claim",
        lazy="select",
        cascade="all, delete-orphan",
    )

    result: Mapped["VerificationResult | None"] = relationship(
        "VerificationResult",
        back_populates="claim",
        lazy="select",
        cascade="all, delete-orphan",
        uselist=False,
    )

    logs: Mapped[list["VerificationLog"]] = relationship(
        "VerificationLog",
        back_populates="claim",
        lazy="select",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_verified_claims_source_status", normalized_source, status),
        Index("ix_verified_claims_status_created", status, sa.text("created_at DESC")),
    )


# ---------------------------------------------------------------------------
# VerificationResult
# ---------------------------------------------------------------------------


class VerificationResult(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Final verdict and scoring breakdown for a verified claim.

    One-to-one with VerifiedClaim. All scoring dimensions from Stages 8-10
    are stored as individual columns for analytical queries.
    """

    __tablename__ = "verification_results"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="FK to verified_claims (UNIQUE — one result per claim)",
    )

    top_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retrieved_articles.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to the highest-ranked supporting evidence article",
    )

    label: Mapped[VerificationLabel] = mapped_column(
        Enum(VerificationLabel, name="verification_label_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Final verdict: TRUE | FALSE | PARTIALLY_TRUE | NOT_FOUND_IN_CLAIMED_SOURCE",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Overall confidence score in [0.0, 1.0]",
    )

    reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable explanation of the verdict and score breakdown",
    )

    semantic_similarity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="LaBSE cosine similarity between claim and best-matching article [0, 1]",
    )

    entity_match: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="NER entity set-intersection ratio between claim and article [0, 1]",
    )

    contradiction_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="NLI contradiction probability from DeBERTa cross-encoder [0, 1]",
    )

    keyword_overlap: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Jaccard similarity of keyword sets between claim and article [0, 1]",
    )

    numerical_consistency: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Proportion of claim numerals that match the article [0, 1]",
    )

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="result",
        lazy="select",
    )

    top_article: Mapped["RetrievedArticle | None"] = relationship(
        "RetrievedArticle",
        back_populates="verification_result",
        lazy="select",
        foreign_keys=[top_article_id],
    )

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"),
        CheckConstraint(
            "semantic_similarity IS NULL OR (semantic_similarity >= 0.0 AND semantic_similarity <= 1.0)",
            name="ck_semantic_similarity_range",
        ),
        CheckConstraint(
            "contradiction_score IS NULL OR (contradiction_score >= 0.0 AND contradiction_score <= 1.0)",
            name="ck_contradiction_score_range",
        ),
        Index("ix_verification_results_label_confidence", label, confidence),
        Index("ix_verification_results_label_created", label, "created_at"),
    )


# ---------------------------------------------------------------------------
# VerificationLog
# ---------------------------------------------------------------------------


class VerificationLog(UUIDMixin, ReprMixin, Base):
    """
    Append-only audit log entry for a single event within a pipeline stage.

    Intentionally write-once (no updated_at) to preserve audit integrity.
    metadata_ stored as JSONB for stage-specific debug payloads.
    """

    __tablename__ = "verification_logs"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to verified_claims — the claim this log entry belongs to",
    )

    stage: Mapped[PipelineStageID] = mapped_column(
        Enum(PipelineStageID, name="pipeline_stage_id_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Pipeline stage that emitted this log: s01_normalizer … s12_persistence",
    )

    level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, name="log_level_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Log severity: INFO | WARNING | ERROR",
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Short human-readable description of the logged event",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        default=dict,
        comment="Stage-specific debug payload as JSONB",
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Milliseconds elapsed in the stage up to this log point",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Log entry timestamp (UTC)",
    )

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="logs",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_verification_logs_claim_stage", claim_id, stage),
        Index("ix_verification_logs_claim_level", claim_id, level),
        Index("ix_verification_logs_stage_level", stage, level),
        Index(
            "ix_verification_logs_metadata_gin",
            metadata_,
            postgresql_using="gin",
        ),
    )
