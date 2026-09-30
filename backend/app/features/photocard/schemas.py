from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import SubmissionStatus
from app.features.verification.schemas import VerificationResponse


class OcrLineSchema(BaseModel):
    """One recognised line, with the reason it was kept or dropped.

    Surfaced so the confirmation screen can show *what* was removed — the user
    is the final authority on whether the extractor got the claim right.
    """

    text: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    bangla_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    is_noise: bool = False
    noise_reason: str | None = Field(
        default=None,
        description=(
            "Why the line was excluded from the claim: social_cta | byline | "
            "credit | timestamp | engagement | copyright | advert | url | "
            "social_handle | phone_number | not_bangla | too_short | "
            "low_confidence | no_letters"
        ),
    )


class DetectedSourceSchema(BaseModel):
    """A verified source the card appears to be attributed to."""

    source_id: uuid.UUID
    canonical_name: str
    display_name: str
    display_name_en: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_text: str = Field(
        ..., description="The OCR fragment that produced the match"
    )
    method: str = Field(..., description="domain | exact | fuzzy")


class PhotoCardExtractResponse(BaseModel):
    """Step 1 result — the extracted claim, awaiting user confirmation.

    Nothing is verified at this point. ``draft_id`` must be sent back to
    ``POST /photocard/verify`` together with the text the user confirmed.
    """

    draft_id: uuid.UUID
    raw_text: str = Field(..., description="Unfiltered OCR output, all lines")
    cleaned_text: str = Field(
        ..., description="OCR text after chrome and non-Bangla lines are removed"
    )
    suggested_headline: str
    suggested_body: str | None = None

    lines: list[OcrLineSchema] = Field(default_factory=list)
    removed_line_count: int = 0

    detected_sources: list[DetectedSourceSchema] = Field(default_factory=list)
    primary_source: DetectedSourceSchema | None = Field(
        default=None,
        description=(
            "Highest-confidence detection, present only when it clears the "
            "auto-select threshold. The user can always override it."
        ),
    )

    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    ocr_engine: str
    bangla_char_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    image_url: str | None = Field(
        default=None, description="Short-lived preview URL, null if storage is down"
    )
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "draft_id": "550e8400-e29b-41d4-a716-446655440000",
                "raw_text": "প্রথম আলো\nবাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস\nফলো করুন @prothomalo",
                "cleaned_text": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস",
                "suggested_headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস",
                "suggested_body": None,
                "removed_line_count": 2,
                "ocr_confidence": 0.88,
                "ocr_engine": "tesseract",
                "bangla_char_ratio": 0.96,
            }
        }
    }


class PhotoCardVerifyRequest(BaseModel):
    """Step 2 input — the claim exactly as the user confirmed it."""

    draft_id: uuid.UUID = Field(
        ..., description="draft_id returned by POST /photocard/extract"
    )
    headline: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Confirmed claim headline, edited by the user if needed",
    )
    body_text: str | None = Field(default=None, max_length=50_000)
    claimed_source_text: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description=(
            "Confirmed source — the canonical name of an active verified source. "
            "Pre-filled from detection when the card was branded."
        ),
    )
    published_date: date | None = None
    force_refresh: bool = False

    @field_validator("headline", "claimed_source_text")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must not be blank after stripping whitespace")
        return stripped

    @field_validator("body_text")
    @classmethod
    def _strip_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    model_config = {
        "json_schema_extra": {
            "example": {
                "draft_id": "550e8400-e29b-41d4-a716-446655440000",
                "headline": "বাংলাদেশে নতুন ডিজিটাল নিরাপত্তা আইন পাস হয়েছে",
                "body_text": None,
                "claimed_source_text": "prothomalo.com",
                "published_date": "2024-03-15",
                "force_refresh": False,
            }
        }
    }


class PhotoCardVerifyResponse(BaseModel):
    """Step 2 result — the verification verdict plus its OCR provenance."""

    submission_id: uuid.UUID
    verification: VerificationResponse
    confirmed_headline: str
    confirmed_body: str | None = None
    ocr_raw_text: str
    ocr_engine: str
    ocr_confidence: float | None = None
    image_url: str | None = None
    detected_source_confidence: float | None = Field(
        default=None,
        description="Confidence of the auto-detected source, if one was detected",
    )
    reused_previous_result: bool = Field(
        default=False,
        description=(
            "True when duplicate detection matched an already-verified claim, so "
            "the earlier result was reused instead of re-running the pipeline."
        ),
    )
    original_submission_id: uuid.UUID | None = Field(
        default=None,
        description="The earlier submission this result was reused from",
    )


class PhotoCardResultResponse(BaseModel):
    """Stored photo-card report, retrieved by submission ID."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    headline: str | None = None
    body_text: str | None = None
    claimed_source_text: str | None = None
    published_date: date | None = None
    ocr_raw_text: str | None = None
    ocr_confirmed_text: str | None = None
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    image_url: str | None = None
    verification: VerificationResponse | None = None
    created_at: datetime
