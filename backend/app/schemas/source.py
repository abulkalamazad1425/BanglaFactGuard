"""
app/schemas/source.py
======================
Pydantic schemas for the source registry CRUD endpoints.

Schema pattern (per CQRS-lite convention):
    SourceCreateSchema  — POST /sources body (write intent)
    SourceUpdateSchema  — PATCH /sources/{id} body (partial update)
    SourceResponseSchema — GET /sources/{id} response (read projection)
    SourceListSchema    — GET /sources response (paginated list)

Design decisions:
- `SourceCreateSchema` makes `aliases` required as a list to ensure the
  normalizer can resolve the source from the very first request.
- `SourceUpdateSchema` uses `model_config = {"extra": "forbid"}` to prevent
  unexpected fields silently being ignored on partial updates.
- `SourceResponseSchema` uses `from_attributes=True` (Pydantic v2 equivalent
  of the old `orm_mode=True`) so it can be constructed directly from a
  SQLAlchemy ORM instance.
- `canonical_name` validation enforces lowercase domain format to match the
  KNOWN_SOURCE_ALIASES map in constants.py.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


# Regex for a simple domain format validation (e.g. prothomalo.com, thedailystar.net)
_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class SourceCreateSchema(BaseModel):
    """
    Request body for registering a new source in the source_registry.

    All Bangla/transliterated aliases should be provided in the `aliases`
    list so that Stage 1 (Normalizer) can resolve them to `canonical_name`.

    Attributes:
        canonical_name: Lowercase domain (e.g. "prothomalo.com").
        display_name:   Human-readable outlet name (e.g. "Prothom Alo").
        aliases:        All alternate names for this source (Bangla + transliterations).
        base_url:       Homepage URL including scheme.
        rss_url:        Optional RSS feed URL.
        language:       Primary language code.
        description:    Optional editorial description.
    """

    canonical_name: str = Field(
        ...,
        min_length=4,
        max_length=255,
        description="Canonical domain name in lowercase (e.g. prothomalo.com)",
        examples=["prothomalo.com", "thedailystar.net"],
    )
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable outlet name (e.g. Prothom Alo)",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description=(
            "All alternate names for this source used in resolution. "
            'Include Bangla script, transliterations, and short forms. '
            'Example: ["প্রথম আলো", "prothom alo", "prothomalo"]'
        ),
    )
    base_url: str = Field(
        ...,
        max_length=512,
        description="Homepage URL including scheme (e.g. https://www.prothomalo.com)",
    )
    rss_url: str | None = Field(
        default=None,
        max_length=512,
        description="RSS feed URL for Google News RSS client (optional)",
    )
    language: str = Field(
        default="bn",
        min_length=2,
        max_length=10,
        description="Primary language code: 'bn' (Bangla) or 'en' (English)",
        examples=["bn", "en"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional editorial description of the news outlet",
    )

    @field_validator("canonical_name")
    @classmethod
    def _validate_canonical_name(cls, v: str) -> str:
        """Enforce lowercase domain format."""
        normalised = v.strip().lower()
        if not _DOMAIN_RE.match(normalised):
            raise ValueError(
                f"canonical_name must be a valid lowercase domain (e.g. prothomalo.com), "
                f"got {v!r}"
            )
        return normalised

    @field_validator("language")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        """Accept only known language codes."""
        allowed = {"bn", "en"}
        lower = v.strip().lower()
        if lower not in allowed:
            raise ValueError(f"language must be one of {allowed}, got {v!r}")
        return lower

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, v: list[str]) -> list[str]:
        """Deduplicate and normalise alias list."""
        seen: set[str] = set()
        result: list[str] = []
        for alias in v:
            clean = alias.strip()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        """Ensure base_url starts with http:// or https://."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    model_config = {
        "json_schema_extra": {
            "example": {
                "canonical_name": "prothomalo.com",
                "display_name": "Prothom Alo",
                "aliases": ["প্রথম আলো", "prothom alo", "prothomalo"],
                "base_url": "https://www.prothomalo.com",
                "rss_url": "https://www.prothomalo.com/feed",
                "language": "bn",
                "description": "Leading Bangla daily newspaper published since 1998.",
            }
        }
    }


class SourceUpdateSchema(BaseModel):
    """
    Request body for partially updating an existing source.

    All fields are optional — only supplied fields are updated.
    Extra fields are forbidden to catch client-side typos.

    Attributes: (all optional versions of SourceCreateSchema fields)
    """

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = Field(default=None)
    base_url: str | None = Field(default=None, max_length=512)
    rss_url: str | None = Field(default=None, max_length=512)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = Field(
        default=None,
        description="Set to false to deactivate this source without deleting it",
    )

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        seen: set[str] = set()
        result: list[str] = []
        for alias in v:
            clean = alias.strip()
            if clean and clean not in seen:
                seen.add(clean)
                result.append(clean)
        return result

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    model_config = {
        "extra": "forbid",
        "json_schema_extra": {
            "example": {
                "is_active": False,
                "aliases": ["প্রথম আলো", "prothom alo", "prothomalo", "pa"],
            }
        },
    }


class SourceResponseSchema(BaseModel):
    """
    Full source record returned by GET /sources/{id} and POST /sources.

    Constructed from a SQLAlchemy SourceRegistry ORM instance via
    `from_attributes=True` (Pydantic v2 ORM mode).

    Attributes: Full set of SourceRegistry columns including audit timestamps.
    """

    id: uuid.UUID = Field(..., description="UUID primary key")
    canonical_name: str = Field(..., description="Canonical domain name")
    display_name: str = Field(..., description="Human-readable outlet name")
    aliases: list[str] = Field(
        default_factory=list,
        description="All alternate names for source resolution",
    )
    base_url: str = Field(..., description="Homepage URL")
    rss_url: str | None = Field(default=None, description="RSS feed URL (if configured)")
    language: str = Field(..., description="Primary language code")
    is_active: bool = Field(..., description="Whether this source is active")
    description: str | None = Field(default=None, description="Editorial description")
    created_at: datetime = Field(..., description="Record creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Record last-update timestamp (UTC)")

    model_config = {
        "from_attributes": True,   # Enable ORM → Pydantic construction
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "canonical_name": "prothomalo.com",
                "display_name": "Prothom Alo",
                "aliases": ["প্রথম আলো", "prothom alo"],
                "base_url": "https://www.prothomalo.com",
                "rss_url": "https://www.prothomalo.com/feed",
                "language": "bn",
                "is_active": True,
                "description": "Leading Bangla daily newspaper published since 1998.",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
            }
        },
    }


class SourceListSchema(BaseModel):
    """
    Paginated list of sources returned by GET /sources.

    Attributes:
        items:   Current page of source records.
        total:   Total number of sources matching the query.
        page:    Current page number (1-based).
        size:    Page size.
        pages:   Total number of pages.
    """

    items: list[SourceResponseSchema] = Field(
        ..., description="Source records for the current page"
    )
    total: int = Field(..., ge=0, description="Total number of matching sources")
    page: int = Field(..., ge=1, description="Current page number (1-based)")
    size: int = Field(..., ge=1, le=100, description="Number of items per page")
    pages: int = Field(..., ge=0, description="Total number of pages")

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "size": 20,
                "pages": 0,
            }
        }
    }
