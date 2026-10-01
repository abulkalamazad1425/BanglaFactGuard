from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    ContentStatus,
    DateStatus,
    ExpertVerdict,
    OverallVerdict,
    SourceStatus,
)
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.submissions.models import Submission
    from app.features.verification.models import VerifiedClaim


class ExpertReview(UUIDMixin, TimestampMixin, ReprMixin, Base):

    __tablename__ = "expert_reviews"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("verified_claims.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ai_label: Mapped[ExpertVerdict] = mapped_column(
        Enum(ExpertVerdict, name="verification_label_enum", create_type=False),
        nullable=False,
        comment="Original AI verdict at time of review",
    )
    expert_label: Mapped[ExpertVerdict] = mapped_column(
        Enum(ExpertVerdict, name="verification_label_enum", create_type=False),
        nullable=False,
        comment="Expert's verdict",
    )
    justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Expert's written justification (min 50 chars)",
    )
    credibility_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="Expert's credibility score at the time of voting",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Review status: pending | finalized",
    )

    claim: Mapped["VerifiedClaim"] = relationship("VerifiedClaim", lazy="select")
    reviewer: Mapped["User | None"] = relationship(
        "User", back_populates="reviews", lazy="select"
    )


class CredibilityScore(UUIDMixin, TimestampMixin, Base):

    __tablename__ = "credibility_scores"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="Current credibility score [0.0 – 1.0]",
    )
    total_votes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of finalized votes by this expert",
    )
    correct_votes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of votes that matched the final verdict",
    )

    user: Mapped["User"] = relationship("User", lazy="select")


class ExpertProfile(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.2 — expert_profiles.

    Additive counterpart to `CredibilityScore` above. Dual-written by
    `CredibilityScoreRepository.get_or_create()` so it stays in sync without any
    change to that method's existing callers/return value.
    """

    __tablename__ = "expert_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    area_of_expertise: Mapped[str] = mapped_column(String(255), nullable=False)
    credential_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    credibility_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    total_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_votes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_reviews_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(
        "User",
        primaryjoin="ExpertProfile.user_id == User.id",
        viewonly=True,
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "credibility_score >= 0.0 AND credibility_score <= 1.0",
            name="ck_expert_profiles_credibility_score_range",
        ),
    )


class CredibilityWeightTier(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.4 — credibility_weight_tiers.

    Note: the PDF's column name `max_accuragy_pct` is a typo in the source
    document; this implementation uses the corrected spelling `max_accuracy_pct`.
    """

    __tablename__ = "credibility_weight_tiers"

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    min_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExpertReviewV2(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """DatabaseDescription.pdf Table 4.11 — expert_reviews (suffixed `_v2` in the DB
    because the legacy `expert_reviews` table, still used by the live voting flow,
    already owns that name).

    The expert votes on the same (source_status, content_status, date_status)
    structure the AI pipeline itself produces — content/date are only
    meaningful (non-null) once source_status is CONFIRMED, mirroring
    s11_classifier's own conditional logic. There is no separate flat
    "verdict" field: finalization writes the consensus straight back onto
    VerificationResultV2.source_status/content_status/date_status.
    """

    __tablename__ = "expert_reviews_v2"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ai_overall_verdict: Mapped[OverallVerdict] = mapped_column(
        Enum(OverallVerdict, name="overall_verdict_enum", create_type=False),
        nullable=False,
        comment="Snapshot of the AI-implied Overall verdict at vote time (all types)",
    )
    ai_source_status: Mapped[SourceStatus | None] = mapped_column(
        Enum(SourceStatus, name="source_status_enum", create_type=False),
        nullable=True,
        comment="Snapshot of the AI's source call at vote time — SOURCE_BASED/PHOTO_CARD only",
    )
    ai_content_status: Mapped[ContentStatus | None] = mapped_column(
        Enum(ContentStatus, name="content_status_enum", create_type=False),
        nullable=True,
    )
    ai_date_status: Mapped[DateStatus | None] = mapped_column(
        Enum(DateStatus, name="date_status_enum", create_type=False),
        nullable=True,
    )
    vote_overall_verdict: Mapped[OverallVerdict] = mapped_column(
        Enum(OverallVerdict, name="overall_verdict_enum", create_type=False),
        nullable=False,
        comment="Expert's own Overall judgment — required for every submission type",
    )
    vote_source_status: Mapped[SourceStatus | None] = mapped_column(
        Enum(SourceStatus, name="source_status_enum", create_type=False),
        nullable=True,
        comment="Expert's own Source judgment — SOURCE_BASED/PHOTO_CARD only",
    )
    vote_content_status: Mapped[ContentStatus | None] = mapped_column(
        Enum(ContentStatus, name="content_status_enum", create_type=False),
        nullable=True,
        comment="Expert's own Content judgment — set only when vote_source_status is CONFIRMED",
    )
    vote_date_status: Mapped[DateStatus | None] = mapped_column(
        Enum(DateStatus, name="date_status_enum", create_type=False),
        nullable=True,
        comment="Expert's own Date judgment — set only when vote_source_status is CONFIRMED",
    )
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    credibility_weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    applied_weight_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("credibility_weight_tiers.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", index=True
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="ExpertReviewV2.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )
    reviewer: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="ExpertReviewV2.reviewer_id == User.id",
        viewonly=True,
        lazy="select",
    )
    applied_weight_tier: Mapped["CredibilityWeightTier | None"] = relationship(
        "CredibilityWeightTier",
        primaryjoin="ExpertReviewV2.applied_weight_tier_id == CredibilityWeightTier.id",
        viewonly=True,
        lazy="select",
    )


class VotingConfig(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Admin-configurable voting parameters — a single-row table (the oldest
    row is always the one in effect) so none of these are fixed settings in
    code. Finalization requires ALL of:
        leader's weighted score   >= verified_threshold        (T)
        number of votes cast      >= min_expert_votes           (M)
        leader's score - runner-up's score >= lead_margin
    checked independently for every applicable dimension (Overall always;
    Source/Content/Date additionally for SOURCE_BASED/PHOTO_CARD, with
    Content/Date skipped once Source's own leader is NOT_FOUND). A claim
    that exhausts max_review_votes or max_review_hours without clearing all
    of the above escalates to admin review instead of finalizing.
    """

    __tablename__ = "voting_config"

    min_expert_votes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        comment="M — minimum number of expert votes before a claim can finalize",
    )
    activation_threshold_votes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment=(
            "N — an expert's vote counts as weight 1.0 until they have "
            "completed this many lifetime votes; their tier weight applies "
            "from then on."
        ),
    )
    verified_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=5.0,
        comment="T — the weighted score the leading verdict must reach, per dimension",
    )
    lead_margin: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Leader's weighted score must exceed the runner-up's by at least this",
    )
    max_review_votes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Escalate to admin after this many votes without reaching consensus (NULL = no cap)",
    )
    max_review_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Escalate to admin after this many hours without reaching consensus (NULL = no cap)",
    )
    max_tier_weight: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Upper bound on any credibility_weight_tiers.weight value (NULL = no cap)",
    )

    __table_args__ = (
        CheckConstraint(
            "min_expert_votes >= 1", name="ck_voting_config_min_votes_positive"
        ),
        CheckConstraint(
            "activation_threshold_votes >= 0",
            name="ck_voting_config_activation_threshold_nonneg",
        ),
        CheckConstraint(
            "verified_threshold > 0", name="ck_voting_config_verified_threshold_positive"
        ),
        CheckConstraint(
            "lead_margin >= 0", name="ck_voting_config_lead_margin_nonneg"
        ),
    )


class AuditLogEntry(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Append-only record of config changes, vote edits, finalizations, and
    credibility updates — nothing reads this to drive behavior, it exists
    purely so admins can answer "why did this happen" after the fact."""

    __tablename__ = "audit_log"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Expert/admin who performed the action; NULL for system-initiated events",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment=(
            "vote_cast | vote_edited | finalized | escalated | "
            "tier_created | tier_updated | tier_deleted | voting_config_updated"
        ),
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submissions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="Free-form context for this event"
    )
