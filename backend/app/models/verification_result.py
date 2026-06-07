"""
app/models/verification_result.py
===================================
ORM model for the `verification_results` table.

Stores the final verdict produced by Stage 11 (Classifier) for a claim.
This is a strict one-to-one relationship with `verified_claims` — each claim
has at most one result row.

All five scoring dimensions from Stage 8-10 are stored as individual columns
(not in a JSONB blob) to enable analytical queries such as:
  "Find all PARTIALLY_TRUE claims where numerical_consistency < 0.5"

Relationships:
    verification_results → verified_claims    (one-to-one, FK on result side)
    verification_results → retrieved_articles (many-to-one, as top_article)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VerificationLabel
from app.models.base import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.retrieved_article import RetrievedArticle
    from app.models.verified_claim import VerifiedClaim


class VerificationResult(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Final verdict and scoring breakdown for a verified claim.

    Attributes:
        claim_id:               FK to verified_claims.id (UNIQUE — one result per claim).
        label:                  Final verdict label.
        confidence:             Overall confidence score in [0.0, 1.0].
        reasoning:              Human-readable explanation of the verdict.
        semantic_similarity:    Stage 8 LaBSE cosine similarity score.
        entity_match:           Stage 8 NER entity set-intersection ratio.
        contradiction_score:    Stage 9 NLI contradiction probability.
        keyword_overlap:        Stage 8 Jaccard keyword overlap ratio.
        numerical_consistency:  Stage 8 custom number-comparison score.
        top_article_id:         FK to the highest-ranked supporting article.
    """

    __tablename__ = "verification_results"

    # --- Foreign keys -------------------------------------------------------

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        unique=True,            # Enforces the one-to-one constraint at DB level
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

    # --- Verdict fields -----------------------------------------------------

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

    # --- Individual scoring dimensions (Stages 8-10) -----------------------

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

    # --- Relationships ------------------------------------------------------

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

    # --- Constraints and indexes --------------------------------------------

    __table_args__ = (
        # Enforce score ranges at DB level
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"),
        CheckConstraint(
            "semantic_similarity IS NULL OR (semantic_similarity >= 0.0 AND semantic_similarity <= 1.0)",
            name="ck_semantic_similarity_range",
        ),
        CheckConstraint(
            "contradiction_score IS NULL OR (contradiction_score >= 0.0 AND contradiction_score <= 1.0)",
            name="ck_contradiction_score_range",
        ),
        # Analytics indexes
        Index("ix_verification_results_label_confidence", label, confidence),
        Index("ix_verification_results_label_created", label, "created_at"),
    )
