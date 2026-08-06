from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.users.models import UserProfile
    from app.features.expert_review.models import ExpertReview


class User(UUIDMixin, TimestampMixin, ReprMixin, Base):

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address — primary login credential",
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Bcrypt-hashed password (NULL for OAuth-only accounts)",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        index=True,
        comment="RBAC role: user | expert | admin",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Email verification status",
    )
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="OAuth provider name: google | facebook | etc.",
    )
    oauth_subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="OAuth provider subject ID",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="DatabaseDescription.pdf Table 4.1 — profile picture URL",
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="DatabaseDescription.pdf Table 4.1 — free-text profile bio",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="DatabaseDescription.pdf Table 4.1 — contact phone number",
    )
    total_submissions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="DatabaseDescription.pdf Table 4.1 — cached submission counter",
    )
    is_email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=(
            "DatabaseDescription.pdf Table 4.1 — additive column, kept separate "
            "from the pre-existing `is_verified` column, which auth flows still "
            "read/write unchanged"
        ),
    )

    profile: Mapped["UserProfile | None"] = relationship(
        "UserProfile",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
        uselist=False,
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        lazy="select",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list["ExpertReview"]] = relationship(
        "ExpertReview",
        back_populates="reviewer",
        lazy="select",
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'expert', 'admin')",
            name="ck_users_role_valid",
        ),
    )


class RefreshToken(UUIDMixin, Base):

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="SHA-256 hash of the refresh token",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class PasswordResetToken(UUIDMixin, Base):

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
