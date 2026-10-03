"""Current submission, source-evidence, retrieved-article and OCR storage.

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

    ocr_extraction: Mapped["OcrExtraction | None"] = relationship(
        "OcrExtraction",
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


class OcrExtraction(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.8 — ocr_extractions."""

    __tablename__ = "ocr_extractions"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    image_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)

    raw_extracted_text: Mapped[str] = mapped_column(Text, nullable=False)

    confirmed_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    ocr_engine: Mapped[str] = mapped_column(
        String(100), nullable=False, default="tesseract-bn"
    )

    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=(
            "Legacy from the two-step extract-then-confirm flow. The "
            "unattended Gemini extraction flow never sets this (there is no "
            "user confirmation step); it stays False on every row it writes."
        ),
    )

    extractor_used: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="GEMINI | EXISTING_FALLBACK — which extractor actually produced the final headline for this card.",
    )

    extraction_model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Gemini model id used (e.g. gemini-2.0-flash), NULL when extractor_used=EXISTING_FALLBACK.",
    )

    extraction_warnings: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Extraction-time warnings as a JSON array of strings — from the "
            "extractor itself (e.g. 'OCR text heavily garbled') and/or a "
            "detected-vs-claimed source/date conflict, which is recorded "
            "here rather than ever silently overriding the user's claimed "
            "source/date."
        ),
    )

    detected_source_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Source/outlet name the extractor found in the card's own text, independent of the user's claimed_source_text — may conflict with it.",
    )

    detected_date_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Publish date text the extractor found in the card's own text, independent of the user's published_date — may conflict with it.",
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        back_populates="ocr_extraction",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0.0 AND ocr_confidence <= 1.0)",
            name="ck_ocr_extractions_confidence_range",
        ),
    )
