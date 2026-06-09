"""
app/features/users/models.py
================================
ORM model for the user profile feature.

Stores extended profile info separate from the core auth.User model.
"""
from __future__ import annotations
import uuid
from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.shared.base_model import Base, TimestampMixin, UUIDMixin
if TYPE_CHECKING:
    from app.features.auth.models import User

class UserProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user: Mapped["User"] = relationship("User", back_populates="profile")
