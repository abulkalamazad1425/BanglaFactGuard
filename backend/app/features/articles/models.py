"""
app/features/articles/models.py
================================
ORM models for the articles feature.

Consolidated from:
  - app/models/retrieved_article.py
  - app/models/search_query.py
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
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ExtractionMethod, QueryType, SearchProvider
from app.shared.base_model import Base, ReprMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.verification.models import VerificationResult, VerifiedClaim


# ---------------------------------------------------------------------------
# RetrievedArticle
# ---------------------------------------------------------------------------


class RetrievedArticle(UUIDMixin, ReprMixin, Base):
    """
    A single candidate article retrieved and extracted for a claim.

    Stores every candidate article fetched and extracted during Stages 5-7.
    The `url_hash` column (SHA-256 of the URL) enables fast duplicate detection.
    """

    __tablename__ = "retrieved_articles"

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

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="retrieved_articles",
        lazy="select",
    )

    verification_result: Mapped["VerificationResult | None"] = relationship(
        "VerificationResult",
        back_populates="top_article",
        lazy="select",
        foreign_keys="VerificationResult.top_article_id",
    )

    __table_args__ = (
        Index(
            "uq_retrieved_articles_claim_url_hash",
            claim_id,
            url_hash,
            unique=True,
        ),
        Index("ix_retrieved_articles_claim_rank", claim_id, rank_score),
        Index("ix_retrieved_articles_extraction_success", claim_id, extraction_success),
    )


# ---------------------------------------------------------------------------
# SearchQuery
# ---------------------------------------------------------------------------


class SearchQuery(UUIDMixin, ReprMixin, Base):
    """
    Records a single search query dispatched during Stage 3/4.

    Write-once audit record — no updated_at column intentionally.
    """

    __tablename__ = "search_queries"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to verified_claims — the claim this query was generated for",
    )

    query_type: Mapped[QueryType] = mapped_column(
        Enum(QueryType, name="query_type_enum", create_type=True),
        nullable=False,
        comment="Category of query: headline | keywords | entities | date_bound | body_summary",
    )

    query_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Exact query string sent to the search provider",
    )

    search_provider: Mapped[SearchProvider] = mapped_column(
        Enum(SearchProvider, name="search_provider_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Which search provider executed this query: google_rss | ddg",
    )

    results_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of result URLs returned by the provider",
    )

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Timestamp when the search query was dispatched (UTC)",
    )

    claim: Mapped["VerifiedClaim"] = relationship(
        "VerifiedClaim",
        back_populates="search_queries",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_search_queries_claim_provider", claim_id, search_provider),
        Index("ix_search_queries_claim_type", claim_id, query_type),
    )

