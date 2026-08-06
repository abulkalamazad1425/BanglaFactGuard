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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VerificationLabel
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
    ai_label: Mapped[VerificationLabel] = mapped_column(
        Enum(VerificationLabel, name="verification_label_enum", create_type=False),
        nullable=False,
        comment="Original AI verdict at time of review",
    )
    expert_label: Mapped[VerificationLabel] = mapped_column(
        Enum(VerificationLabel, name="verification_label_enum", create_type=False),
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
    already owns that name)."""

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
    ai_label: Mapped[str] = mapped_column(String(20), nullable=False)
    expert_label: Mapped[VerificationLabel] = mapped_column(
        Enum(VerificationLabel, name="verification_label_enum", create_type=False),
        nullable=False,
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
