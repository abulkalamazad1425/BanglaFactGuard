from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineAlterationStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionType,
)


class SubmissionSummary(BaseModel):
    """One row of My Submissions. Valid for a submission that has no result
    or even no headline yet (a just-accepted photo card)."""

    submission_id: str
    submission_type: SubmissionType = SubmissionType.SOURCE_BASED
    headline: str | None
    claimed_source_text: str | None
    status: str
    phase: str | None = None
    failure_reason: str | None = None
    source_status: SourceStatus | None
    content_status: ContentStatus | None
    headline_status: HeadlineAlterationStatus | None = None
    date_status: DateStatus | None = None
    published_date: date | None = None
    # Expert-finalized only; None while the claim is still under review.
    overall_verdict: OverallVerdict | None = None
    prediction: str | None = None
    is_finalized: bool = False
    ai_confidence: float | None
    image_url: str | None = None
    submitted_at: datetime
    updated_at: datetime | None = None


class SubmissionStatsResponse(BaseModel):
    total: int
    source_confirmed: int
    source_not_found: int
    content_matched: int
    content_altered: int
    pending: int


class ProfileResponse(BaseModel):
    id: str
    full_name: str | None
    email: str
    role: str
    is_active: bool
    total_submissions: int
    member_since: datetime


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
