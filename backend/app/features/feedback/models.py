"""
app/features/feedback/models.py
Stores user feedback on verification results.
"""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.base_model import Base, TimestampMixin, UUIDMixin
import uuid

class UserFeedback(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_feedback"
    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verified_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="User rating 1-5")
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="agree | disagree | unclear | other")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

