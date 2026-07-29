
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column







class Base(DeclarativeBase):



    type_annotation_map: dict = {}







class UUIDMixin:

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Primary key — UUID v4 generated in Python before INSERT",
    )


class TimestampMixin:

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="Row creation timestamp (UTC, set by DB on INSERT)",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Row last-update timestamp (UTC, auto-updated by DB on UPDATE)",
    )


class ReprMixin:

    def __repr__(self) -> str:
        pk_val = getattr(self, "id", "?")
        return f"<{self.__class__.__name__} id={pk_val!s}>"
