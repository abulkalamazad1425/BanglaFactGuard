"""
app/features/expert_review/models.py
=======================================
ORM models for the expert review feature.

Experts (journalists, fact-checkers) can manually review
AI-generated verification verdicts and override them.

Tables:
    expert_reviews - Manual review records linked to a verified claim
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import VerificationLabel
from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.auth.models import User
    from app.features.verification.models import VerifiedClaim


class ExpertReview(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    A manual expert override of an AI verification verdict.

    Allows certified fact-checkers to override or validate the pipeline verdict.
    """

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
        comment="Original AI verdict",
    )
    expert_label: Mapped[VerificationLabel] = mapped_column(
        Enum(VerificationLabel, name="verification_label_enum", create_type=False),
        nullable=False,
        comment="Expert's revised verdict",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Expert's reasoning and notes",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Review status: pending | approved | rejected",
    )

    claim: Mapped["VerifiedClaim"] = relationship("VerifiedClaim", lazy="select")
    reviewer: Mapped["User | None"] = relationship(
        "User", back_populates="reviews", lazy="select"
    )
