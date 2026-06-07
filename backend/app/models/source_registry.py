"""
app/models/source_registry.py
==============================
ORM model for the `source_registry` table.

Stores the canonical registry of known Bangla/English news sources.
Used by Stage 1 (Normalizer) to resolve raw claimed source strings
(e.g. "প্রথম আলো", "prothom alo") to canonical domains (e.g. "prothomalo.com").

Relationships:
    source_registry → verified_claims  (one-to-many, via claimed_source FK)
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.verified_claim import VerifiedClaim


class SourceRegistry(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Registry of known news sources with canonical domain names and aliases.

    Each row represents one authoritative news outlet. The `aliases` JSONB
    column stores an array of all known alternate names (Bangla script,
    transliterations, short names) used for fuzzy resolution.

    Attributes:
        canonical_name:  Primary domain identifier (e.g. "prothomalo.com").
                         UNIQUE — used as the FK target from verified_claims.
        display_name:    Human-readable outlet name (e.g. "Prothom Alo").
        aliases:         JSONB array of all known alternate names for this source.
                         GIN-indexed for fast containment queries.
        base_url:        Homepage URL (e.g. "https://www.prothomalo.com").
        rss_url:         Optional RSS feed URL for Google RSS client.
        language:        Primary language code ("bn" for Bangla, "en" for English).
        is_active:       Whether this source is currently used for verification.
    """

    __tablename__ = "source_registry"

    # --- Core fields --------------------------------------------------------

    canonical_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Canonical domain name (e.g. prothomalo.com) — unique identifier",
    )

    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Human-readable outlet name (e.g. Prothom Alo)",
    )

    aliases: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment='JSONB array of alternate names, e.g. ["প্রথম আলো", "prothom alo"]',
    )

    base_url: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Homepage URL (e.g. https://www.prothomalo.com)",
    )

    rss_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="RSS feed URL for Google News RSS client (optional)",
    )

    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="bn",
        comment="Primary language code: 'bn' (Bangla) or 'en' (English)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether this source is active and eligible for verification",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional editorial description of the news outlet",
    )

    # --- Relationships ------------------------------------------------------

    claims: Mapped[list["VerifiedClaim"]] = relationship(
        "VerifiedClaim",
        back_populates="source",
        lazy="select",
        cascade="save-update, merge",
    )

    # --- Composite indexes --------------------------------------------------

    __table_args__ = (
        # GIN index on aliases JSONB for fast containment queries:
        # WHERE aliases @> '["প্রথম আলো"]'
        Index(
            "ix_source_registry_aliases_gin",
            aliases,
            postgresql_using="gin",
        ),
        Index("ix_source_registry_language_active", language, is_active),
    )
