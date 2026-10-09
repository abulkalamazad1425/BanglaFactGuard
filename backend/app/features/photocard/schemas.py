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
    failure_reason, a completed one has the saved verification.

    The headline, claimed outlet and claimed date are what Gemini read from
    the card - there is no separate user-entered source or date."""

    submission_id: uuid.UUID
    status: SubmissionStatus
    phase: str | None = None
    failure_reason: str | None = None
    claim_scope: ClaimScope = ClaimScope.HEADLINE_ONLY

    headline: str | None = Field(
        default=None, description="The headline exactly as printed on the card; the only text verified."
    )
    claimed_source_text: str | None = Field(
        default=None,
        description="Canonical id of the active verified source identified on the card - the verification target.",
    )
    claimed_source_name: str | None = Field(default=None, description="Display name of that source.")
    detected_source_text: str | None = Field(
        default=None,
        description=(
            "Outlet text visible on the card as read by the extractor. Provenance only: when "
            "it is not an active verified source the card is checked against the verified sources."
        ),
    )
    published_date: date | None = Field(
        default=None,
        description="Publication date printed on the card - the claimed date. Null when the card shows no complete date.",
    )

    extraction_status: str | None = Field(
        default=None, description="PENDING | SUCCEEDED | API_FAILED | INVALID_CONTENT"
    )
    extraction_attempts: int | None = Field(
        default=None, description="Gemini requests made (first request included, at most 9)."
    )
    extraction_model_version: str | None = None
    extraction_failures: list[str] = Field(
        default_factory=list, description="Short, user-presentable reasons for failed reading attempts."
    )
    image_url: str | None = None

    verification: VerificationResponse | None = None
    created_at: datetime
