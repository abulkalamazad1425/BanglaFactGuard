from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ContentStatus, DateStatus, ExpertVerdict, OverallVerdict, SourceStatus
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.submissions.models import RetrievedArticle, Submission


class VerificationResult(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Stored source-based or photo-card analysis for one submission."""

    __tablename__ = "verification_results"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    ai_preliminary_label: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    source_status: Mapped[SourceStatus | None] = mapped_column(
        Enum(SourceStatus, name="source_status_enum", create_type=True),
        nullable=True,
        index=True,
        comment=(
            "The AI pipeline's own call — an immutable snapshot, written once "
            "by the verification pipeline and never overwritten by expert review. See "
            "final_source_status for the expert-finalized value, which may "
            "differ from this one."
        ),
    )

    content_status: Mapped[ContentStatus | None] = mapped_column(
        Enum(ContentStatus, name="content_status_enum", create_type=True),
        nullable=True,
        comment=(
            "Headline Alteration verdict (MATCHED | ALTERED): the claim headline "
            "vs the selected source TITLE only. The AI's own call — immutable, "
            "see source_status. NULL when no verdict was reached; "
            "headline_check_status says why."
        ),
    )

    headline_check_status: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment=(
            "HeadlineCheckStatus: COMPLETED | SOURCE_NOT_FOUND | SOURCE_CHECK_INCOMPLETE "
            "| SOURCE_TITLE_MISSING | MODEL_UNAVAILABLE | UNDETERMINED. Processing "
            "status of the headline check, separate from the verdict."
        ),
    )

    headline_exact_match: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="True when the headline verdict came from an exact match with the source title.",
    )

    body_comparison_status: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
        comment=(
            "BodyComparisonStatus: COMPUTED | SKIPPED | UNAVAILABLE. The four body "
            "similarity scores themselves live in analysis_details.body_similarity."
        ),
    )

    date_status: Mapped[DateStatus | None] = mapped_column(
        Enum(DateStatus, name="date_status_enum", create_type=True),
        nullable=True,
        comment=(
            "The AI's own call — immutable, see source_status. Only set when "
            "both dates are known; independent of content_status — a mismatch "
            "here does not imply false content."
        ),
    )

    final_source_status: Mapped[SourceStatus | None] = mapped_column(
        Enum(SourceStatus, name="source_status_enum", create_type=False),
        nullable=True,
        comment="Expert-finalized Source verdict — NULL until finalized. Written only by ExpertReviewService.",
    )

    final_content_status: Mapped[ContentStatus | None] = mapped_column(
        Enum(ContentStatus, name="content_status_enum", create_type=False),
        nullable=True,
        comment="Expert-finalized Headline Alteration verdict — NULL until finalized, or if final_source_status is NOT_FOUND.",
    )

    final_date_status: Mapped[DateStatus | None] = mapped_column(
        Enum(DateStatus, name="date_status_enum", create_type=False),
        nullable=True,
        comment="Expert-finalized Date verdict — NULL until finalized, or if final_source_status is NOT_FOUND.",
    )

    overall_verdict: Mapped[OverallVerdict | None] = mapped_column(
        Enum(OverallVerdict, name="overall_verdict_enum", create_type=False),
        nullable=True,
        index=True,
        comment=(
            "Expert-finalized Overall verdict (Fake/Real/Misleading/Altered) — "
            "NULL until expert review finalizes this claim. Functionally the "
            "'final_overall_verdict' of this fields group — named before "
            "final_source/content/date_status existed. Written only by "
            "ExpertReviewService, never by the AI pipeline itself."
        ),
    )

    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When expert review finalized this claim; NULL until then.",
    )

    ai_consensus_label: Mapped[ExpertVerdict | None] = mapped_column(
        Enum(ExpertVerdict, name="verification_label_enum", create_type=False),
        nullable=True,
        index=True,
        comment=(
            "LEGACY / NO LONGER WRITTEN. Formerly a single-category projection "
            "of (source_status, content_status) onto TRUE/FALSE/PARTIALLY_TRUE. "
            "The automated system casts no overall truth vote, so new rows "
            "leave this NULL; historical values are kept, never erased. See "
            "verdict_compat.py."
        ),
    )

    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    top_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retrieved_articles.id", ondelete="SET NULL"),
        nullable=True,
    )

    avg_verification_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Source-correspondence measurements (NULL = no measurement) ──────────
    headline_similarity: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="LaBSE cosine of claim headline vs selected source title (correspondence)."
    )
    headline_keyword_coverage: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Share of claim keywords found in the source title (correspondence)."
    )
    passage_keyword_coverage: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Share of claim keywords found in the title + relevant source passages (correspondence)."
    )

    claim_scope: Mapped[str | None] = mapped_column(
        String(24),
        nullable=True,
        comment="HEADLINE_ONLY | HEADLINE_WITH_BODY — the scope this result was computed under.",
    )
    pipeline_version: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
        comment="VERIFICATION_PIPELINE_VERSION in force when computed. NULL on rows from before the scope-aware rewrite; those are never reused as fresh results.",
    )
    analysis_details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "AnalysisDetails payload: correspondence measurements, search "
            "accounting, source basis, Headline Alteration detail, body "
            "similarity scores, date analysis and timings. Durable source for "
            "result display after the Redis entry expires."
        ),
    )
    reused_from_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when this result row is an automated-result copy of an earlier identical verification.",
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="VerificationResult.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )

    top_article: Mapped["RetrievedArticle | None"] = relationship(
        "RetrievedArticle",
        primaryjoin="VerificationResult.top_article_id == RetrievedArticle.id",
        viewonly=True,
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_verification_results_confidence_range",
        ),
        Index(
            "ix_verification_results_status_created",
            source_status,
            content_status,
            "created_at",
        ),
    )


class VerificationJob(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Durable unit of background verification work.

    The row is written in the same transaction as the accepted submission, so
    an accepted submission can never exist without its job. A worker claims
    jobs with ``FOR UPDATE SKIP LOCKED`` and stamps ``locked_at``; a job whose
    lock has gone stale (process crashed or restarted mid-run) is reclaimed on
    the next poll. Nothing about execution depends on the browser, polling, or
    the request that created it.
    """

    __tablename__ = "verification_jobs"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="SOURCE_BASED | PHOTO_CARD | MULTIMODAL"
    )
    status: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        default="QUEUED",
        index=True,
        comment="QUEUED | RUNNING | DONE | FAILED",
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Job inputs that are not on the submission row.",
    )

    __table_args__ = (Index("ix_verification_jobs_status_created", status, "created_at"),)
