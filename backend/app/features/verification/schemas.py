"""
app/features/verification/schemas.py
======================================
Pydantic schemas for the verification feature.

Consolidated from:
  - app/schemas/verification.py
  - app/schemas/scores.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import ClaimStatus, VerificationLabel
from app.features.articles.schemas import RankedArticleSchema


# ---------------------------------------------------------------------------
# Scores & Manipulation Flags (from scores.py)
# ---------------------------------------------------------------------------


class NLIScoresSchema(BaseModel):
    """Raw NLI output triple from the DeBERTa cross-encoder (Stage 9)."""

    entailment: float = Field(..., ge=0.0, le=1.0, description="NLI entailment probability")
    contradiction: float = Field(..., ge=0.0, le=1.0, description="NLI contradiction probability")
    neutral: float = Field(..., ge=0.0, le=1.0, description="NLI neutral probability")

    model_config = {
        "json_schema_extra": {
            "example": {"entailment": 0.87, "contradiction": 0.05, "neutral": 0.08}
        }
    }


class VerificationScoresSchema(BaseModel):
    """Aggregated multi-dimensional evidence scores for a verification result."""

    semantic_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    entity_match: float | None = Field(default=None, ge=0.0, le=1.0)
    keyword_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    numerical_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # Pre-computed sub-dimensions exposed for S10 and S11
    headline_similarity: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="LaBSE cosine similarity between claim headline and article title only.",
    )
    body_similarity: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="LaBSE cosine similarity between claim full text and article body only.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "semantic_similarity": 0.91,
                "entity_match": 0.85,
                "keyword_overlap": 0.78,
                "numerical_consistency": 1.0,
                "contradiction_score": 0.04,
            }
        }
    }


class ManipulationFlagsSchema(BaseModel):
    """Boolean flags produced by Stage 10 (Manipulation Detector)."""

    headline_manipulated: bool = Field(default=False)
    body_altered: bool = Field(default=False)
    numbers_altered: bool = Field(default=False)
    entities_replaced: bool = Field(default=False)

    @property
    def any_manipulation_detected(self) -> bool:
        """Return True if any manipulation flag is set."""
        return any([
            self.headline_manipulated,
            self.body_altered,
            self.numbers_altered,
            self.entities_replaced,
        ])

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline_manipulated": True,
                "body_altered": False,
                "numbers_altered": False,
                "entities_replaced": False,
            }
        }
    }


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class VerificationRequest(BaseModel):
    """Input body for POST /api/v1/verify."""

    headline: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The article headline being claimed.",
        examples=["বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"],
    )
    news_body: str | None = Field(default=None, max_length=50_000)
    claimed_source: str = Field(..., min_length=1, max_length=255)
    published_date: date | None = Field(default=None, examples=["2024-03-15"])
    force_refresh: bool = Field(default=False)

    @field_validator("headline")
    @classmethod
    def _strip_headline(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("headline must not be blank after stripping whitespace")
        return stripped

    @field_validator("claimed_source")
    @classmethod
    def _strip_claimed_source(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("claimed_source must not be blank")
        return stripped

    @field_validator("news_body")
    @classmethod
    def _strip_news_body(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে",
                "news_body": "জাতীয় সংসদে আজ বিকেলে ডিজিটাল নিরাপত্তা আইনের সংশোধনী প্রস্তাব সর্বসম্মতিক্রমে পাস হয়েছে।",
                "claimed_source": "প্রথম আলো",
                "published_date": "2024-03-15",
                "force_refresh": False,
            }
        }
    }


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class VerificationScoresResponse(VerificationScoresSchema):
    """Scores as returned in the API response."""
    pass


class VerificationResponse(BaseModel):
    """Full response body for POST /api/v1/verify and GET /api/v1/verify/{id}."""

    claim_id: uuid.UUID
    label: VerificationLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    matched_articles: list[RankedArticleSchema] = Field(default_factory=list)
    scores: VerificationScoresResponse
    manipulation_flags: ManipulationFlagsSchema = Field(
        default_factory=ManipulationFlagsSchema
    )
    normalized_source: str | None = None
    cached: bool = False
    processing_time_ms: int | None = None
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440000",
                "label": "TRUE",
                "confidence": 0.92,
                "reasoning": "Prothom Alo published a matching article on 2024-03-15.",
                "matched_articles": [],
                "scores": {
                    "semantic_similarity": 0.91,
                    "entity_match": 0.88,
                    "keyword_overlap": 0.79,
                    "numerical_consistency": 1.0,
                    "contradiction_score": 0.04,
                },
                "manipulation_flags": {
                    "headline_manipulated": False,
                    "body_altered": False,
                    "numbers_altered": False,
                    "entities_replaced": False,
                },
                "normalized_source": "prothomalo.com",
                "cached": False,
                "processing_time_ms": 4231,
                "created_at": "2024-03-15T12:00:00Z",
            }
        }
    }


class VerificationResultSummary(BaseModel):
    """Compact summary for embedding in list responses or notifications."""

    claim_id: uuid.UUID
    headline: str = Field(..., max_length=200)
    label: VerificationLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    claimed_source: str
    normalized_source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationStatusResponse(BaseModel):
    """Lightweight response for GET /api/v1/verify/{claim_id}/status."""

    claim_id: uuid.UUID
    status: ClaimStatus
    result: VerificationResponse | None = None
    error: str | None = None
    queued_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "processing",
                "result": None,
                "error": None,
                "queued_at": "2024-03-15T12:00:00Z",
                "updated_at": "2024-03-15T12:00:03Z",
            }
        }
    }
