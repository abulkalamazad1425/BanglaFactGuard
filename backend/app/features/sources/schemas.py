"""
app/features/sources/schemas.py
=================================
Pydantic schemas for the sources feature.

Migrated from: app/schemas/source.py
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


_DOMAIN_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
)


class SourceCreateSchema(BaseModel):
    """Request body for registering a new source in the source_registry."""

    canonical_name: str = Field(
        ...,
        min_length=4,
        max_length=255,
        description="Canonical domain name in lowercase (e.g. prothomalo.com)",
        examples=["prothomalo.com", "thedailystar.net"],
    )
    display_name: str = Field(..., min_length=1, max_length=255)
    aliases: list[str] = Field(default_factory=list)
    base_url: str = Field(..., max_length=512)
    rss_url: str | None = Field(default=None, max_length=512)
    language: str = Field(default="bn", min_length=2, max_length=10, examples=["bn", "en"])
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("canonical_name")
    @classmethod
    def _validate_canonical_name(cls, v: str) -> str:
        normalised = v.strip().lower()
        if not _DOMAIN_RE.match(normalised):
            raise ValueError(
                f"canonical_name must be a valid lowercase domain (e.g. prothomalo.com), got {v!r}"
            )
        return normalised

    @field_validator("language")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        allowed = {"bn", "en"}
        lower = v.strip().lower()
        if lower not in allowed:
            raise ValueError(f"language must be one of {allowed}, got {v!r}")
        return lower

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, v: list[str]) -> list[str]:
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
    """Request body for partially updating an existing source."""

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    aliases: list[str] | None = Field(default=None)
    base_url: str | None = Field(default=None, max_length=512)
    rss_url: str | None = Field(default=None, max_length=512)
    language: str | None = Field(default=None, min_length=2, max_length=10)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = Field(default=None)

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
    """Full source record returned by GET /sources/{id} and POST /sources."""

    id: uuid.UUID
    canonical_name: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    base_url: str
    rss_url: str | None = None
    language: str
    is_active: bool
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
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
    """Paginated list of sources returned by GET /sources."""

    items: list[SourceResponseSchema]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    size: int = Field(..., ge=1, le=100)
    pages: int = Field(..., ge=0)

    model_config = {
        "json_schema_extra": {
            "example": {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}
        }
    }
