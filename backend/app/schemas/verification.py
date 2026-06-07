"""
app/schemas/verification.py
============================
Pydantic schemas for the primary verification API:
  POST /api/v1/verify  →  VerificationRequest → VerificationResponse

Also provides:
  GET  /api/v1/verify/{claim_id}  →  VerificationStatusResponse
  (lightweight status + summary for polling long-running verifications)

Schema hierarchy:
    VerificationRequest            — API input (POST body)
    VerificationResponse           — Full API output (final verdict)
    VerificationResultSummary      — Compact result for embedding in lists
    VerificationStatusResponse     — Status-check response (polling endpoint)

Design decisions:
- Input text fields have conservative max-length limits matching `AppSettings`
  (`max_headline_length=2000`, `max_body_length=50_000`). These are enforced
  at the schema layer before any NLP processing begins.
- `claimed_source` is a raw free-text field (no validation against the DB) —
  resolution happens in Stage 1 (Normalizer). This allows the API to accept
  partial/misspelled source names gracefully.
- `published_date` is `date | None` with ISO-8601 string input accepted via
  Pydantic's automatic date coercion (accepts "2024-03-15", datetime objects).
- `VerificationResponse.matched_articles` holds a list of `RankedArticleSchema`
  objects — the top-K evidence articles used in the decision.
- `processing_time_ms` is populated by the orchestrator to expose end-to-end
  latency in the response, helping clients identify slow queries.
- `force_refresh` in the request allows callers to bypass the cache and trigger
  a fresh pipeline run — useful for re-checking a claim after new articles
  are published.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.constants import ClaimStatus, VerificationLabel
from app.schemas.article import RankedArticleSchema
from app.schemas.scores import ManipulationFlagsSchema, VerificationScoresSchema


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class VerificationRequest(BaseModel):
    """
    Input body for POST /api/v1/verify.

    Represents a single claim to be fact-checked against the stated source.

    Attributes:
        headline:       The article headline or title being claimed.
                        Must be non-empty after stripping whitespace.
        news_body:      Full article body text (optional but strongly recommended
                        for higher-accuracy results).
        claimed_source: The news outlet the Facebook post or claim attributes
                        as the publisher. Raw text — normalised in Stage 1.
        published_date: Optional date the article was allegedly published.
                        Narrows the search window in Stage 3.
        force_refresh:  If True, bypass Redis and DB cache and run the full
                        pipeline even if a cached result exists.
    """

    headline: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The article headline being claimed. Must be at least 5 characters.",
        examples=["বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"],
    )
    news_body: str | None = Field(
        default=None,
        max_length=50_000,
        description=(
            "Full article body text. Optional but recommended for better accuracy. "
            "Enables body-level similarity and manipulation detection."
        ),
    )
    claimed_source: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "The news outlet claimed as the publisher. "
            "Accepts Bangla script, transliterations, or domain names. "
            'Examples: "প্রথম আলো", "prothom alo", "prothomalo.com"'
        ),
        examples=["প্রথম আলো", "The Daily Star", "prothomalo.com"],
    )
    published_date: date | None = Field(
        default=None,
        description=(
            "Alleged publication date (ISO-8601: YYYY-MM-DD). "
            "Used to constrain search queries to a date window."
        ),
        examples=["2024-03-15"],
    )
    force_refresh: bool = Field(
        default=False,
        description=(
            "If True, bypass cached results and run the full verification pipeline. "
            "Use when checking if a previously verified claim has new evidence."
        ),
    )

    @field_validator("headline")
    @classmethod
    def _strip_headline(cls, v: str) -> str:
        """Strip leading/trailing whitespace from headline."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("headline must not be blank after stripping whitespace")
        return stripped

    @field_validator("claimed_source")
    @classmethod
    def _strip_claimed_source(cls, v: str) -> str:
        """Strip leading/trailing whitespace from claimed_source."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("claimed_source must not be blank")
        return stripped

    @field_validator("news_body")
    @classmethod
    def _strip_news_body(cls, v: str | None) -> str | None:
        """Normalise empty strings to None for consistent downstream handling."""
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে",
                "news_body": (
                    "জাতীয় সংসদে আজ বিকেলে ডিজিটাল নিরাপত্তা আইনের সংশোধনী "
                    "প্রস্তাব সর্বসম্মতিক্রমে পাস হয়েছে। আইনমন্ত্রী জানিয়েছেন..."
                ),
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
    """
    Scores as returned in the API response.
    Identical to VerificationScoresSchema — named separately for clarity
    in the OpenAPI docs.
    """
    pass


class VerificationResponse(BaseModel):
    """
    Full response body for POST /api/v1/verify and GET /api/v1/verify/{id}.

    Attributes:
        claim_id:           UUID of the verified_claims record.
        label:              Final verdict.
        confidence:         Overall confidence score in [0.0, 1.0].
        reasoning:          Human-readable explanation of the verdict.
        matched_articles:   Top-K ranked evidence articles used in the decision.
        scores:             Detailed multi-dimensional scoring breakdown.
        manipulation_flags: Boolean flags for detected manipulation types.
        normalized_source:  Resolved canonical domain for the claimed source.
        cached:             True if this result was served from cache (not re-computed).
        processing_time_ms: End-to-end pipeline latency in milliseconds (None if cached).
        created_at:         Timestamp when the verification was first completed.
    """

    claim_id: uuid.UUID = Field(
        ...,
        description="UUID of the verified_claims DB record for this result",
    )
    label: VerificationLabel = Field(
        ...,
        description="Final verdict: TRUE | FALSE | PARTIALLY_TRUE | NOT_FOUND_IN_CLAIMED_SOURCE",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score for the verdict [0.0, 1.0]",
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of how the verdict was reached",
    )
    matched_articles: list[RankedArticleSchema] = Field(
        default_factory=list,
        description="Top-K ranked evidence articles used in the verification decision",
    )
    scores: VerificationScoresResponse = Field(
        ...,
        description="Multi-dimensional scoring breakdown from Stages 8–10",
    )
    manipulation_flags: ManipulationFlagsSchema = Field(
        default_factory=ManipulationFlagsSchema,
        description="Boolean flags for each type of detected content manipulation",
    )
    normalized_source: str | None = Field(
        default=None,
        description="Resolved canonical domain (e.g. prothomalo.com)",
    )
    cached: bool = Field(
        default=False,
        description="True if this result was served from Redis or DB cache",
    )
    processing_time_ms: int | None = Field(
        default=None,
        description="Full pipeline end-to-end latency in milliseconds (None for cached results)",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when this verification result was first generated (UTC)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "claim_id": "550e8400-e29b-41d4-a716-446655440000",
                "label": "TRUE",
                "confidence": 0.92,
                "reasoning": (
                    "Prothom Alo published a matching article on 2024-03-15. "
                    "Semantic similarity: 0.91. All entities match. No contradiction detected."
                ),
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
    """
    Compact summary of a verification result for embedding in list responses
    or notifications. Does NOT include matched_articles or detailed scores.

    Used by:
    - GET /sources/{id}/claims (list of claims per source)
    - Background job status notifications

    Attributes:
        claim_id:          UUID of the verified_claims record.
        headline:          First 200 chars of the original headline.
        label:             Final verdict label.
        confidence:        Overall confidence score.
        claimed_source:    Raw claimed source string (as submitted).
        normalized_source: Resolved canonical domain.
        created_at:        Verification timestamp.
    """

    claim_id: uuid.UUID
    headline: str = Field(..., max_length=200)
    label: VerificationLabel
    confidence: float = Field(..., ge=0.0, le=1.0)
    claimed_source: str
    normalized_source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationStatusResponse(BaseModel):
    """
    Lightweight response for GET /api/v1/verify/{claim_id}/status.

    Used to poll the status of an in-progress or queued verification
    without fetching the full result. Returns the full `VerificationResponse`
    only when status is COMPLETED.

    Attributes:
        claim_id:   UUID of the claim.
        status:     Current pipeline lifecycle state.
        result:     Full verification result (populated only when COMPLETED).
        error:      Error message (populated only when FAILED).
        queued_at:  When the request was first received.
        updated_at: When the status was last updated.
    """

    claim_id: uuid.UUID = Field(..., description="UUID of the claim")
    status: ClaimStatus = Field(
        ...,
        description="Pipeline status: pending | processing | completed | failed",
    )
    result: VerificationResponse | None = Field(
        default=None,
        description="Full result — populated only when status=completed",
    )
    error: str | None = Field(
        default=None,
        description="Error message — populated only when status=failed",
    )
    queued_at: datetime = Field(..., description="When this request was first received (UTC)")
    updated_at: datetime = Field(..., description="When the status was last updated (UTC)")

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
