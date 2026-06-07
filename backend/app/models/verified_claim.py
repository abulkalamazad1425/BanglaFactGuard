"""
app/models/verified_claim.py
=============================
ORM model for the `verified_claims` table.

Central table that records every unique fact-checking request submitted
to the system. A claim is uniquely identified by `claim_hash` (SHA-256
of the normalised headline + source), which enables cache-hit detection
at the DB level (Stage 2 cache lookup).

Relationships:
    verified_claims → source_registry         (many-to-one, via normalized_source)
    verified_claims → search_queries          (one-to-many)
    verified_claims → retrieved_articles      (one-to-many)
    verified_claims → verification_result     (one-to-one)
    verified_claims → verification_logs       (one-to-many)
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ClaimStatus
from app.models.base import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.retrieved_article import RetrievedArticle
    from app.models.search_query import SearchQuery
    from app.models.source_registry import SourceRegistry
    from app.models.verification_log import VerificationLog
    from app.models.verification_result import VerificationResult


class VerifiedClaim(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Records a single fact-checking request and its lifecycle state.

    The `claim_hash` column is the deduplication key: before running the
    full pipeline, the system checks whether a result for this hash already
    exists (Stage 2 DB cache lookup).

    Attributes:
        claim_hash:         SHA-256 hex digest of normalised (headline + claimed_source).
                            Enables O(1) duplicate detection.
        headline:           Raw input headline from the request.
        news_body:          Raw input news body (may be empty).
        claimed_source:     Raw user-supplied source string (e.g. "প্রথম আলো").
        normalized_source:  Resolved canonical domain (e.g. "prothomalo.com").
        source_id:          FK to source_registry.id (nullable — set if resolved).
        published_date:     Optional date the article was allegedly published.
        status:             Pipeline lifecycle state (pending → processing → completed/failed).
    """

    __tablename__ = "verified_claims"

    # --- Core fields --------------------------------------------------------

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

    # --- Relationships ------------------------------------------------------

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
        uselist=False,  # One-to-one
    )

    logs: Mapped[list["VerificationLog"]] = relationship(
        "VerificationLog",
        back_populates="claim",
        lazy="select",
        cascade="all, delete-orphan",
    )

    # --- Composite indexes --------------------------------------------------

    __table_args__ = (
        Index("ix_verified_claims_source_status", normalized_source, status),
        Index("ix_verified_claims_status_created", status, sa.text("created_at DESC")),
    )
