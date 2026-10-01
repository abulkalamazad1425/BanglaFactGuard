from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import (
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
)
from app.features.articles.schemas import RankedArticleSchema


class NLIScoresSchema(BaseModel):

    entailment: float = Field(
        ..., ge=0.0, le=1.0, description="NLI entailment probability"
    )
    contradiction: float = Field(
        ..., ge=0.0, le=1.0, description="NLI contradiction probability"
    )
    neutral: float = Field(..., ge=0.0, le=1.0, description="NLI neutral probability")

    model_config = {
        "json_schema_extra": {
            "example": {"entailment": 0.87, "contradiction": 0.05, "neutral": 0.08}
        }
    }


class VerificationScoresSchema(BaseModel):

    semantic_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    entity_match: float | None = Field(default=None, ge=0.0, le=1.0)
    keyword_overlap: float | None = Field(default=None, ge=0.0, le=1.0)
    numerical_consistency: float | None = Field(default=None, ge=0.0, le=1.0)
    contradiction_score: float | None = Field(default=None, ge=0.0, le=1.0)

    headline_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="LaBSE cosine similarity between claim headline and article title only.",
    )
    body_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
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

    headline_manipulated: bool = Field(default=False)
    body_altered: bool = Field(default=False)
    numbers_altered: bool = Field(default=False)
    entities_replaced: bool = Field(default=False)

    @property
    def any_manipulation_detected(self) -> bool:
        return any(
            [
                self.headline_manipulated,
                self.body_altered,
                self.numbers_altered,
                self.entities_replaced,
            ]
        )

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


class VerificationRequest(BaseModel):

    headline: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="The article headline being claimed.",
        examples=["বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে"],
    )
    body_text: str | None = Field(default=None, max_length=50_000)
    claimed_source_text: str = Field(..., min_length=1, max_length=255)
    published_date: date | None = Field(default=None, examples=["2024-03-15"])
    force_refresh: bool = Field(default=False)

    @field_validator("headline")
    @classmethod
    def _strip_headline(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("headline must not be blank after stripping whitespace")
        return stripped

    @field_validator("claimed_source_text")
    @classmethod
    def _strip_claimed_source(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("claimed_source_text must not be blank")
        return stripped

    @field_validator("body_text")
    @classmethod
    def _strip_body_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    model_config = {
        "json_schema_extra": {
            "example": {
                "headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে",
                "body_text": "জাতীয় সংসদে আজ বিকেলে ডিজিটাল নিরাপত্তা আইনের সংশোধনী প্রস্তাব সর্বসম্মতিক্রমে পাস হয়েছে।",
                "claimed_source_text": "প্রথম আলো",
                "published_date": "2024-03-15",
                "force_refresh": False,
            }
        }
    }


class VerificationScoresResponse(VerificationScoresSchema):
    pass


class VerificationResponse(BaseModel):

    submission_id: uuid.UUID
    overall_verdict: OverallVerdict | None = Field(
        default=None,
        description=(
            "The displayed Overall verdict — the expert-finalized value if "
            "available, otherwise the AI's preliminary implied value."
        ),
    )
    is_finalized: bool = Field(
        default=False,
        description="True once expert review has finalized overall_verdict.",
    )
    was_overridden: bool = Field(
        default=False,
        description="True if expert review's finalized verdict differs from the AI's original call.",
    )
    ai_overall_verdict: OverallVerdict | None = Field(
        default=None,
        description="The AI's own implied Overall verdict, before any expert override.",
    )
    ai_source_status: SourceStatus | None = Field(
        default=None,
        description="The AI's own original call — immutable, never changed by expert review.",
    )
    ai_content_status: ContentStatus | None = Field(default=None)
    ai_date_status: DateStatus | None = Field(default=None)
    source_status: SourceStatus = Field(
        ...,
        description=(
            "The displayed Source verdict — expert-finalized if available, "
            "otherwise the AI's call (see ai_source_status for the AI's "
            "original, which this may now differ from)."
        ),
    )
    content_status: ContentStatus | None = Field(
        default=None,
        description=(
            "How the claimed content compares to the source. Only set when "
            "source_status is CONFIRMED — there is nothing to compare "
            "against when the source never published the story."
        ),
    )
    date_status: DateStatus | None = Field(
        default=None,
        description=(
            "Whether the claimed publication date matches the source "
            "article's actual date. Only set when both dates are known; a "
            "mismatch does not imply the content itself is false."
        ),
    )
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
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_status": "CONFIRMED",
                "content_status": "MATCHED",
                "date_status": "MISMATCHED",
                "confidence": 0.92,
                "reasoning": (
                    "Prothom Alo published a matching article, but on a "
                    "different date than claimed."
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

    submission_id: uuid.UUID
    headline: str = Field(..., max_length=200)
    source_status: SourceStatus
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    claimed_source_text: str
    normalized_source: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationQueuedResponse(BaseModel):
    """Acknowledgement for a claim accepted for background verification.

    The pipeline takes up to a minute or so, which is far too long to hold a
    user on the form. The claim is registered immediately and this identifier
    is what the caller polls (or revisits from their history) for the result.
    """

    submission_id: uuid.UUID
    status: SubmissionStatus
    cached: bool = Field(
        default=False,
        description=(
            "True when this exact claim had already been verified and the "
            "stored result is being reused instead of re-running the pipeline."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PENDING",
                "cached": False,
            }
        }
    }


class VerificationStatusResponse(BaseModel):

    submission_id: uuid.UUID
    status: SubmissionStatus
    result: VerificationResponse | None = None
    error: str | None = None
    queued_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "submission_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "PROCESSING",
                "result": None,
                "error": None,
                "queued_at": "2024-03-15T12:00:00Z",
                "updated_at": "2024-03-15T12:00:03Z",
            }
        }
    }
