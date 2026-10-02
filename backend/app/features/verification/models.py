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
    ContentStatus,
    DateStatus,
    ExpertVerdict,
    LogLevel,
    OverallVerdict,
    PipelineStageID,
    SourceStatus,
)
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.articles.models import RetrievedArticle, SearchQuery
    from app.features.sources.models import VerifiedSource
    from app.features.submissions.models import RetrievedArticleV2, Submission


class VerifiedClaim(UUIDMixin, TimestampMixin, ReprMixin, Base):

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
        ForeignKey("verified_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to verified_sources.id — set when source is successfully resolved",
    )

    published_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Alleged publication date supplied in the request (optional)",
    )

    submitter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="FK to users.id — NULL for anonymous submissions",
    )

    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status_enum", create_type=True),
        nullable=False,
        default=ClaimStatus.PENDING,
        index=True,
        comment="Pipeline lifecycle state: pending → processing → completed/failed",
    )

    source: Mapped["VerifiedSource | None"] = relationship(
        "VerifiedSource",
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

    __table_args__ = (
        Index("ix_verified_claims_source_status", normalized_source, status),
        Index("ix_verified_claims_status_created", status, sa.text("created_at DESC")),
    )


class VerificationResult(UUIDMixin, TimestampMixin, ReprMixin, Base):

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

    label: Mapped[ExpertVerdict] = mapped_column(
        Enum(ExpertVerdict, name="verification_label_enum", create_type=True),
        nullable=False,
        index=True,
        comment=(
            "Legacy single-category verdict: TRUE | FALSE | PARTIALLY_TRUE | "
            "NOT_FOUND_IN_CLAIMED_SOURCE. This table predates the pipeline's "
            "current (source_status, content_status, date_status) model — see "
            "VerificationResultV2 for the live schema."
        ),
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
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"
        ),
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


class VerificationLog(UUIDMixin, ReprMixin, Base):
    """Pipeline-internal observability log — no DatabaseDescription.pdf counterpart.
    Repointed from verified_claims to submissions (column renamed claim_id ->
    submission_id) since it's actively written on every live pipeline run."""

    __tablename__ = "verification_logs"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to submissions — the submission this log entry belongs to",
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

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="VerificationLog.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )

    __table_args__ = (
        Index("ix_verification_logs_submission_stage", submission_id, stage),
        Index("ix_verification_logs_submission_level", submission_id, level),
        Index("ix_verification_logs_stage_level", stage, level),
        Index(
            "ix_verification_logs_metadata_gin",
            metadata_,
            postgresql_using="gin",
        ),
    )


class VerificationResultV2(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.10 — verification_results (suffixed `_v2` in the
    DB because the legacy `verification_results` table, still used by the live
    pipeline, already owns that name)."""

    __tablename__ = "verification_results_v2"

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
            "by s11_classifier.py and never overwritten by expert review. See "
            "final_source_status for the expert-finalized value, which may "
            "differ from this one."
        ),
    )

    content_status: Mapped[ContentStatus | None] = mapped_column(
        Enum(ContentStatus, name="content_status_enum", create_type=True),
        nullable=True,
        comment=(
            "The AI's own call — immutable, see source_status. Only set when "
            "source_status is CONFIRMED."
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
        comment="Expert-finalized Content verdict — NULL until finalized, or if final_source_status is NOT_FOUND.",
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
        ForeignKey("retrieved_articles_v2.id", ondelete="SET NULL"),
        nullable=True,
    )

    semantic_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    entity_match: Mapped[float | None] = mapped_column(Float, nullable=True)

    contradiction_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    keyword_overlap: Mapped[float | None] = mapped_column(Float, nullable=True)

    numerical_consistency: Mapped[float | None] = mapped_column(Float, nullable=True)

    avg_verification_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Component scores (applicable ones only; NULL = no measurement) ──────
    headline_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_similarity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Submitted body vs aligned source passages. NULL for HEADLINE_ONLY claims (always for photo cards).",
    )
    passage_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    headline_keyword_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    passage_keyword_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    body_keyword_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)

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
            "AnalysisDetails payload: metric states and diagnostics, selected "
            "evidence passages, NLI output, search accounting, date "
            "provenance and the decision basis. Durable source for result "
            "display after the Redis entry expires."
        ),
    )
    reused_from_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        comment="Set when this result row is an automated-result copy of an earlier identical verification.",
    )

    manipulation_flags: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "Full ManipulationFlagsSchema payload (the 4 booleans plus "
            "altered_numbers/substituted_entities detail) from s10_"
            "manipulation_detector.py's last run. NULL on rows written "
            "before this column existed, or when S10 never ran. Previously "
            "this only ever lived in the Redis result cache and was lost "
            "once that entry's TTL expired — GET /verify/{id} would then "
            "silently show no manipulation detected even when the original "
            "run found some, with nothing to show experts reviewing an "
            "older claim. This column is now the durable, authoritative "
            "source; the Redis cache remains a fast-path best-effort read "
            "for a fresh result."
        ),
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="VerificationResultV2.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )

    top_article: Mapped["RetrievedArticleV2 | None"] = relationship(
        "RetrievedArticleV2",
        primaryjoin="VerificationResultV2.top_article_id == RetrievedArticleV2.id",
        viewonly=True,
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="ck_verification_results_v2_confidence_range",
        ),
        CheckConstraint(
            "semantic_similarity IS NULL OR (semantic_similarity >= 0.0 AND semantic_similarity <= 1.0)",
            name="ck_verification_results_v2_semantic_similarity_range",
        ),
        CheckConstraint(
            "contradiction_score IS NULL OR (contradiction_score >= 0.0 AND contradiction_score <= 1.0)",
            name="ck_verification_results_v2_contradiction_score_range",
        ),
        Index(
            "ix_verification_results_v2_status_created",
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
        String(20), nullable=False, comment="SOURCE_BASED | PHOTO_CARD"
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
        comment="Job inputs that are not on the submission row (force_refresh, ...).",
    )

    __table_args__ = (Index("ix_verification_jobs_status_created", status, "created_at"),)
