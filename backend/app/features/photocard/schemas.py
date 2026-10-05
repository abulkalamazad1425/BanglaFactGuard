from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.constants import ClaimScope, SubmissionStatus
from app.features.verification.schemas import VerificationResponse


class PhotoCardAcceptedResponse(BaseModel):
    """HTTP 202 acknowledgement. The card is stored and the job is durable;
    extraction and verification continue on the server whether or not the
    client stays on the page. Fetch current state by `submission_id`."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = Field(default=None, description="QUEUED | EXTRACTING | VERIFYING | DONE | FAILED")
    message: str
    queued_at: datetime


class PhotoCardResultResponse(BaseModel):
    """Stored photo-card report, retrieved by submission ID. Valid in every
    state: a pending row has no headline/verification yet, a failed one has a
    failure_reason, a completed one has the saved verification."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = None
    failure_reason: str | None = None
    claim_scope: ClaimScope = ClaimScope.HEADLINE_ONLY

    headline: str | None = Field(
        default=None, description="The extracted headline exactly as returned by the extractor; the only text verified."
    )
    claimed_source_text: str | None = Field(
        default=None, description="The outlet the USER selected - the verification target."
    )
    published_date: date | None = Field(
        default=None, description="The date the USER supplied - the only date compared with the source."
    )

    extraction_method: str | None = Field(
        default=None, description="GEMINI_IMAGE | OCR_FALLBACK (null until extraction finished or when it failed)."
    )
    extraction_attempts: int | None = Field(
        default=None, description="Gemini attempts made (first request included, at most 3)."
    )
    fallback_used: bool = Field(default=False, description="True when EasyOCR + the fallback extractor ran.")
    extraction_model_version: str | None = None
    extraction_failures: list[str] = Field(
        default_factory=list, description="Short, user-presentable reasons for failed extraction attempts."
    )
    extraction_warnings: list[str] = Field(default_factory=list)
    extracted_date_text: str | None = Field(
        default=None,
        description="Date printed on the card, raw. Display only - never compared. Null when the card shows none.",
    )
    extracted_source_text: str | None = Field(
        default=None,
        description="Outlet name printed on the card, raw. Display only - never compared. Null when none is visible.",
    )

    ocr_raw_text: str | None = Field(default=None, description="EasyOCR text (fallback path only).")
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    image_url: str | None = None

    verification: VerificationResponse | None = None
    created_at: datetime
