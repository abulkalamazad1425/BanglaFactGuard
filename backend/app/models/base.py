"""
app/models/base.py
==================
SQLAlchemy 2.0 declarative base and shared ORM mixins.

Design decisions:
- `Base` uses the modern `DeclarativeBase` class (SQLAlchemy 2.0 style),
  not the legacy `declarative_base()` factory. This enables full type-hinting
  via `Mapped` and `mapped_column` across all models.
- `UUIDMixin` generates UUIDs server-side in Python (not DB-side) so that
  the primary key is always known before the INSERT, enabling pre-association
  of related records without a round-trip.
- `TimestampMixin` uses `DateTime(timezone=True)` (TIMESTAMPTZ in PostgreSQL)
  for all temporal columns — critical for multi-timezone deployments.
- `created_at` uses `server_default=func.now()` so the DB sets it on INSERT;
  `updated_at` additionally sets `onupdate=func.now()` for automatic updates.
- `__tablename__` is NOT defined on Base or mixins — each concrete model must
  declare it explicitly, which makes the codebase self-documenting.
- `repr_columns` is a hook for generating clean `__repr__` output without
  loading lazy relationships.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Declarative Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base class for all ORM models.

    All models in `app/models/` must inherit from this class.
    The `metadata` attribute is shared and used by Alembic for migrations.
    """

    # Type annotation map — tells SQLAlchemy how to resolve Python types
    # to SQL column types when using `Mapped[T]` annotations.
    type_annotation_map: dict = {}  # extended by models as needed


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class UUIDMixin:
    """
    Adds a UUID v4 primary key column named `id`.

    The UUID is generated in Python (server-side) using `uuid.uuid4()` so
    that the value is always known before the row is inserted into the DB.
    This enables pre-associating related objects without a DB round-trip.

    Column type: `UUID(as_uuid=True)` which maps to PostgreSQL's native
    `uuid` type for efficient storage and indexing.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Primary key — UUID v4 generated in Python before INSERT",
    )


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` TIMESTAMPTZ columns to a model.

    - `created_at` is set by the database server on INSERT via `server_default`.
    - `updated_at` is refreshed by the database server on every UPDATE via
      `onupdate`, removing the need for application-level timestamp management.
    - Both columns use `timezone=True` (PostgreSQL TIMESTAMPTZ) to store UTC
      offsets, preventing ambiguity across DST transitions.
    """

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
    """
    Adds a clean `__repr__` that shows the class name and primary key,
    without triggering any lazy relationship loads.
    """

    def __repr__(self) -> str:  # pragma: no cover
        pk_val = getattr(self, "id", "?")
        return f"<{self.__class__.__name__} id={pk_val!s}>"
