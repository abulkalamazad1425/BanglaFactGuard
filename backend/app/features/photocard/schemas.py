from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.constants import ClaimScope, SubmissionStatus
from app.features.verification.schemas import VerificationResponse


class DetectedSourceSchema(BaseModel):
    """A verified source the card's branding appears to match."""

    source_id: uuid.UUID
    canonical_name: str
    display_name: str
    display_name_en: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    matched_text: str = Field(
        ..., description="The OCR fragment that produced the match"
    )
    method: str = Field(..., description="domain | exact | fuzzy")


class PhotoCardAcceptedResponse(BaseModel):
    """HTTP 202 acknowledgement. The card is stored and the job is durable;
    OCR, extraction and verification continue on the server whether or not
    the client stays on the page. Fetch current state by `submission_id`."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = Field(default=None, description="QUEUED | EXTRACTING | VERIFYING | DONE | FAILED")
    message: str
    queued_at: datetime


class PhotoCardVerifyResponse(BaseModel):
    """The single unattended flow's result: OCR → headline extraction
    (Gemini, falling back to the deterministic extractor) → the shared
    verification pipeline, run against the extracted headline and the
    user's own claimed_source_text/published_date — no confirmation step in
    between."""

    submission_id: uuid.UUID
    verification: VerificationResponse

    extracted_headline: str = Field(
        ..., description="The headline the claim was actually verified against."
    )
    extractor_used: str = Field(
        ..., description="GEMINI | EXISTING_FALLBACK — which extractor produced it."
    )
    extraction_model_version: str | None = Field(
        default=None,
        description="Gemini model id used, null when extractor_used=EXISTING_FALLBACK.",
    )
    extraction_warnings: list[str] = Field(default_factory=list)

    detected_sources: list[DetectedSourceSchema] = Field(
        default_factory=list,
        description="Verified sources the card's own branding matched (independent of the claimed_source_text the user provided).",
    )
    detected_source_text: str | None = Field(
        default=None,
        description=(
            "Source/outlet name the extractor found in the card's own text. "
            "Never silently substituted for the user's claimed_source_text — "
            "see source_date_conflict if the two disagree."
        ),
    )
    detected_date_text: str | None = Field(
        default=None,
        description=(
            "Archival date text read from the card. Not compared with any "
            "date, not displayed by the clients, and never used for warnings."
        ),
    )
    source_date_conflict: bool = Field(
        default=False,
        description="Legacy field name: now only indicates detected source disagreement. Extracted dates never trigger a conflict.",
    )

    ocr_raw_text: str
    ocr_engine: str
    ocr_confidence: float | None = None
    image_url: str | None = None

    claimed_source_text: str
    published_date: date | None = None

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
    """Stored photo-card report, retrieved by submission ID. Valid in every
    state: a pending row has no headline/verification yet, a failed one has a
    failure_reason, a completed one has the saved verification."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = None
    failure_reason: str | None = None
    claim_scope: ClaimScope = ClaimScope.HEADLINE_ONLY
    headline: str | None = None
    claimed_source_text: str | None = None
    published_date: date | None = None

    ocr_raw_text: str | None = None
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    image_url: str | None = None

    extractor_used: str | None = None
    extraction_model_version: str | None = None
    extraction_warnings: list[str] = Field(default_factory=list)
    detected_source_text: str | None = None
    detected_date_text: str | None = None
    source_date_conflict: bool = False

    verification: VerificationResponse | None = None
    created_at: datetime
