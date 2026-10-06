from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ContentStatus, DateStatus, OverallVerdict, SourceStatus
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.submissions.models import Submission


class ExpertProfile(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Current expert credibility and review statistics."""

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
    credibility_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, default=None
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
  
    __tablename__ = "credibility_weight_tiers"

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    min_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_accuracy_pct: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ExpertReview(UUIDMixin, TimestampMixin, ReprMixin, Base):

    __tablename__ = "expert_reviews"

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
    ai_overall_verdict: Mapped[OverallVerdict | None] = mapped_column(
        Enum(OverallVerdict, name="overall_verdict_enum", create_type=False),
        nullable=True,
        comment=(
            "Snapshot of the AI-implied Overall verdict at vote time — "
            "MULTIMODAL only. Automated checks never produce an Overall "
            "verdict for SOURCE_BASED/PHOTO_CARD, so this is NULL for them."
        ),
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
    is_admin_decision: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment=(
            "True for the administrator's decision on an ESCALATED claim. That "
            "overall vote IS the final verdict; earlier expert votes cannot "
            "override it."
        ),
    )

    submission: Mapped["Submission"] = relationship(
        "Submission",
        primaryjoin="ExpertReview.submission_id == Submission.id",
        viewonly=True,
        lazy="select",
    )
    reviewer: Mapped["User | None"] = relationship(
        "User",
        primaryjoin="ExpertReview.reviewer_id == User.id",
        viewonly=True,
        lazy="select",
    )
    applied_weight_tier: Mapped["CredibilityWeightTier | None"] = relationship(
        "CredibilityWeightTier",
        primaryjoin="ExpertReview.applied_weight_tier_id == CredibilityWeightTier.id",
        viewonly=True,
        lazy="select",
    )


class VotingConfig(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """Admin-configurable voting parameters — a single-row table (the oldest
    row is always the one in effect) so none of these are fixed settings in
    code.

    Only the reviewers' OVERALL vote (Real/Fake/Misleading/Altered) decides a
    claim. It finalizes when ALL of these hold for the weighted overall tally:
        leader's weighted score   >= verified_threshold        (T)
        number of votes cast      >= min_expert_votes           (M)
        leader's score - runner-up's score >= lead_margin
        the leader is unique (an exact tie never finalizes)
    The supplementary source/headline/date assessments are recorded for
    reference only and never affect finalization or escalation.

    Escalation: a claim still undecided ESCALATES to admin review as soon as
    ANY configured limit is exceeded — votes cast >= max_review_votes, OR
    hours since submission >= max_review_hours. A NULL limit is "not
    configured" and is never treated as exceeded; with both NULL a claim stays
    in expert review until it reaches consensus. The time limit is enforced
    by a background sweep (`escalation.py`), so it does not depend on a new
    vote or a page visit.
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
