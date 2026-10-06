"""Current submission, source-evidence, retrieved-article and photo-card extraction storage.

These models are used by the live text, photo-card and multimodal workflows.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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

from app.core.constants import ExtractionMethod, QueryType, SearchProvider, SubmissionStatus, SubmissionType
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.sources.models import VerifiedSource


class Submission(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.5 — submissions."""

    __tablename__ = "submissions"

    submission_type: Mapped[SubmissionType] = mapped_column(
        Enum(SubmissionType, name="submission_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="MULTIMODAL | SOURCE_BASED | PHOTO_CARD",
    )

    headline: Mapped[str | None] = mapped_column(Text, nullable=True)

    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    claimed_source_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Raw source string as provided by the user",
    )

    claimed_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    submitter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="SHA-256 hex of normalised submission content — dedup key",
    )

    duplicate_of_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Self-referential FK — set when this submission is a duplicate of another",
    )

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status_enum", create_type=True),
        nullable=False,
        default=SubmissionStatus.PENDING,
        index=True,
    )

    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    processing_phase: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment=(
            "Finer progress inside PENDING/PROCESSING (QUEUED | EXTRACTING | "
            "VERIFYING | DONE | FAILED). The public lifecycle enum is unchanged."
        ),
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Short, user-presentable reason when status is FAILED (e.g. no readable headline in the image).",
    )

    escalated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When expert review escalated this claim to admin review (NULL otherwise).",
    )

    claimed_source: Mapped["VerifiedSource | None"] = relationship(
        "VerifiedSource",
        primaryjoin="Submission.claimed_source_id == VerifiedSource.id",
        viewonly=True,
        lazy="select",
    )

    submitter: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="Submission.submitter_id == User.id",
        viewonly=True,
        lazy="select",
    )

    evidence_queries: Mapped[list["SourceEvidenceQuery"]] = relationship(
        "SourceEvidenceQuery",
        back_populates="submission",
        lazy="select",
        cascade="all, delete-orphan",
    )

    retrieved_articles: Mapped[list["RetrievedArticle"]] = relationship(
        "RetrievedArticle",
        back_populates="submission",
        lazy="select",
        cascade="all, delete-orphan",
    )

    photocard_extraction: Mapped["PhotocardExtraction | None"] = relationship(
        "PhotocardExtraction",
        back_populates="submission",
        lazy="select",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_submissions_status_created", status, "created_at"),
    )


class SourceEvidenceQuery(UUIDMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.6 — source_evidence_queries."""

    __tablename__ = "source_evidence_queries"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    query_type: Mapped[QueryType] = mapped_column(
        Enum(QueryType, name="query_type_enum", create_type=False),
        nullable=False,
    )

    query_text: Mapped[str] = mapped_column(Text, nullable=False)

    search_provider: Mapped[SearchProvider] = mapped_column(
        Enum(SearchProvider, name="search_provider_enum", create_type=False),
        nullable=False,
        index=True,
    )

    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="evidence_queries",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_source_evidence_queries_submission_provider", submission_id, search_provider),
    )


class RetrievedArticle(UUIDMixin, ReprMixin, Base):
    """Retrieved source evidence for a submission."""

    __tablename__ = "retrieved_articles"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    url: Mapped[str] = mapped_column(Text, nullable=False)

    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    author: Mapped[str | None] = mapped_column(String(255), nullable=True)

    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method_enum", create_type=False),
        nullable=True,
    )

    extraction_success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )

    rank_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="retrieved_articles",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "rank_score IS NULL OR (rank_score >= 0.0 AND rank_score <= 1.0)",
            name="ck_retrieved_articles_rank_score_range",
        ),
        Index(
            "uq_retrieved_articles_submission_url_hash",
            submission_id,
            url_hash,
            unique=True,
        ),
    )


class PhotocardExtraction(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Gemini extraction of a photo card (one row per PHOTO_CARD submission).

    The extracted headline, verified source and published date are NOT
    stored here: on success they become the submission's own headline,
    claimed_source_id/claimed_source_text and published_date - the single
    representation of the claim. This row keeps the stored image and the
    extraction provenance only.
    """

    __tablename__ = "photocard_extractions"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    image_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
        comment=(
            "PENDING | SUCCEEDED | API_FAILED (every Gemini request failed) | "
            "INVALID_CONTENT (no headline or no active verified source on the card) | "
            "FAILED (legacy OCR-era failure)"
        ),
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="gemini_unavailable | headline_missing | source_not_identified | headline_and_source_missing",
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Gemini model id that read the card.",
    )

    attempts: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Gemini requests made for this card (first request included, at most 9).",
    )

    extraction_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Provenance: per-attempt Gemini outcomes, the validated raw response "
            "(headline, source id + visible evidence, date as printed) and the parsed "
            "date. Legacy OCR-era values are kept under 'legacy'."
        ),
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="photocard_extraction",
        lazy="select",
    )
