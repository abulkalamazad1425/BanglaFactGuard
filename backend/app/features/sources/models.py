"""
app/features/sources/models.py
================================
ORM model for the sources feature.

Migrated from: app/models/source_registry.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, ReprMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.features.verification.models import VerifiedClaim


class VerifiedSource(UUIDMixin, TimestampMixin, ReprMixin, Base):
    """
    Registry of verified news sources with canonical domain names, aliases, and scraping configurations.

    Used by Stage 1 (Normalizer) to resolve raw claimed source strings
    (e.g. "প্রথম আলো", "prothom alo") to canonical domains (e.g. "prothomalo.com").
    Also used by Stage 6 (Article Extractor) to fetch article scraping configurations.
    """

    __tablename__ = "verified_sources"

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
        JSON().with_variant(JSONB, "postgresql"),
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

    body_selectors: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        comment="CSS selectors for extracting article body",
    )

    title_selectors: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        comment="CSS selectors for extracting article title",
    )

    date_selectors: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        comment="CSS selectors for extracting published date",
    )

    internal_search_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="URL template for internal site search (e.g. .../search?q={query})",
    )

    article_url_patterns: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        comment="Regex patterns to match valid article URLs",
    )

    claims: Mapped[list["VerifiedClaim"]] = relationship(
        "VerifiedClaim",
        back_populates="source",
        lazy="select",
        cascade="save-update, merge",
    )

    __table_args__ = (
        Index(
            "ix_verified_sources_aliases_gin",
            aliases,
            postgresql_using="gin",
        ),
        Index("ix_verified_sources_language_active", language, is_active),
    )
