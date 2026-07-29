
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VerificationLabel
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
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
