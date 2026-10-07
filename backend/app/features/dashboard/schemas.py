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


class MethodDistribution(BaseModel):
    source_based: int
    multimodal: int
    photo_card: int


class PublicStatsResponse(BaseModel):
    total_submissions: int
    source_confirmed_count: int
    source_not_found_count: int
    content_matched_count: int
    content_altered_count: int
    date_matched_count: int
    date_mismatched_count: int
    pending_count: int
    method_distribution: MethodDistribution
    avg_verification_time_seconds: float | None


class TopSourceItem(BaseModel):
    source: str
    count: int


class ExplorerItem(BaseModel):
    prediction: str | None = None
    submission_id: str
    headline: str | None
    submission_type: SubmissionType
    claimed_source_text: str | None
    overall_verdict: OverallVerdict | None = Field(
        default=None,
        description=(
            "The expert-finalized Overall verdict. NULL until expert review "
            "finalizes the claim - the automated system never sets it."
        ),
    )
    is_finalized: bool = Field(
        default=False,
        description="True once expert review has finalized overall_verdict.",
    )
    # Preliminary AI findings (never the final verdict). Cards show the
    # headline status, the date comparison only when a date was claimed, and
    # the source finding only when no relevant article was found.
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    headline_status: HeadlineAlterationStatus | None = None
    date_status: DateStatus | None = None
    confidence: float | None
    image_url: str | None = Field(
        default=None, description="Thumbnail for MULTIMODAL/PHOTO_CARD submissions"
    )
    published_date: date | None
    created_at: datetime


class ExplorerSearchResponse(BaseModel):
    items: list[ExplorerItem]
    total: int
    limit: int
    offset: int
    archive_summary: dict[str, int] = Field(default_factory=dict)
