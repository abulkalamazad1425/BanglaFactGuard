"""
app/models/retrieved_article.py
================================
ORM model for the `retrieved_articles` table.

Stores every candidate article fetched and extracted during Stages 5-7.
Each row represents one URL that was retrieved for a particular claim, with
its extracted content, metadata, and ranking score.

The `url_hash` column (SHA-256 of the URL) enables fast duplicate detection
within a claim — preventing the same article being processed twice if it
appears in results from multiple query variants.

Relationships:
    retrieved_articles → verified_claims       (many-to-one)
    retrieved_articles → verification_results  (one-to-one, as top_article_id)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ExtractionMethod
from app.models.base import Base, ReprMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.verified_claim import VerifiedClaim
    from app.models.verification_result import VerificationResult


class RetrievedArticle(UUIDMixin, ReprMixin, Base):
    """
    A single candidate article retrieved and extracted for a claim.

    Attributes:
        claim_id:            FK to the parent verified_claim.
        url:                 Full URL of the retrieved article.
        url_hash:            SHA-256 of the URL — used for dedup within a claim.
        title:               Extracted article title (may differ from the claim headline).
        body:                Extracted article body text.
        author:              Extracted author byline (if available).
        published_date:      Extracted publication date (if parseable).
        extraction_method:   Which extractor was used: trafilatura or beautifulsoup.
        extraction_success:  Whether extraction produced usable content.
        rank_score:          Stage 7 ranking score in [0.0, 1.0].
        retrieved_at:        Timestamp when this URL was processed.
    """

    __tablename__ = "retrieved_articles"

    # --- Core fields --------------------------------------------------------

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to verified_claims — the claim this article was retrieved for",
    )

    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full URL of the retrieved candidate article",
    )

    url_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 of the URL — used for deduplication within a claim",
    )

    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted article title",
    )

    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted full article body text",
    )

    author: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Extracted author byline (if available in the article metadata)",
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Publication date extracted from the article (if parseable)",
    )

    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method_enum", create_type=True),
        nullable=True,
        comment="Which extraction backend produced this content: trafilatura | beautifulsoup",
    )

    extraction_success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if extraction produced content exceeding the minimum length threshold",
    )

    rank_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        index=True,
        comment="Stage 7 evidence ranking score in [0.0, 1.0] — higher is more relevant",
    )

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when this URL was fetched and processed (UTC)",
    )

    # --- Relationships ------------------------------------------------------

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="retrieved_articles",
        lazy="select",
    )

    # Back-ref from VerificationResult.top_article (not a cascade target)
    verification_result: Mapped["VerificationResult | None"] = relationship(
        "VerificationResult",
        back_populates="top_article",
        lazy="select",
        foreign_keys="VerificationResult.top_article_id",
    )

    # --- Composite indexes --------------------------------------------------

    __table_args__ = (
        # Unique URL per claim — prevents processing same article twice
        Index(
            "uq_retrieved_articles_claim_url_hash",
            claim_id,
            url_hash,
            unique=True,
        ),
        Index("ix_retrieved_articles_claim_rank", claim_id, rank_score),
        Index("ix_retrieved_articles_extraction_success", claim_id, extraction_success),
    )
