from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.core.constants import (
    ContentStatus,
    DateStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionType,
)


class ExpertVoteRequest(BaseModel):
    """An expert's vote. overall_verdict is required for every submission
    type. source_status (plus, conditionally, content_status/date_status)
    additionally applies to SOURCE_BASED/PHOTO_CARD claims only — whether
    it's required or must be omitted depends on the submission's type, which
    this schema doesn't know, so that cross-check happens in the service
    layer; the validator below only enforces internal consistency (content/
    date present exactly when source_status is CONFIRMED)."""

    overall_verdict: OverallVerdict
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    justification: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Expert's written justification for the verdict (min 50 characters)",
    )

    @model_validator(mode="after")
    def _check_conditional_fields(self) -> "ExpertVoteRequest":
        if self.source_status == SourceStatus.CONFIRMED:
            if self.content_status is None or self.date_status is None:
                raise ValueError(
                    "content_status and date_status are required when source_status is CONFIRMED"
                )
        elif self.source_status == SourceStatus.NOT_FOUND:
            if self.content_status is not None or self.date_status is not None:
                raise ValueError(
                    "content_status and date_status must be omitted when source_status is NOT_FOUND"
                )
        return self


class ExpertVoteUpdateRequest(BaseModel):
    overall_verdict: OverallVerdict | None = None
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    justification: str | None = Field(default=None, min_length=50, max_length=5000)


class ExpertReviewResponse(BaseModel):
    id: str
    submission_id: str
    reviewer_id: str | None
    ai_overall_verdict: OverallVerdict
    ai_source_status: SourceStatus | None
    ai_content_status: ContentStatus | None
    ai_date_status: DateStatus | None
    vote_overall_verdict: OverallVerdict
    vote_source_status: SourceStatus | None
    vote_content_status: ContentStatus | None
    vote_date_status: DateStatus | None
    justification: str | None
    credibility_weight: float
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExpertTopArticle(BaseModel):
    url: str
    title: str | None = None
    published_date: str | None = None
    rank_score: float | None = None
    body_snippet: str | None = None


class ExpertQueueItemResponse(BaseModel):
    submission_id: str
    submission_type: SubmissionType
    headline: str | None
    body_text: str | None = None
    claimed_source_text: str | None
    ai_label: str | None = Field(
        default=None,
        description="Human-readable summary of the AI's call, for display.",
    )
    ai_overall_verdict: OverallVerdict | None = None
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    ai_confidence: float | None
    submitted_at: datetime
    vote_count: int
    top_article: ExpertTopArticle | None = None
    image_url: str | None = Field(
        default=None, description="Multimodal submissions only — the submitted card/photo"
    )


class ExpertHistoryItemResponse(BaseModel):
    review_id: str
    submission_id: str
    submission_type: SubmissionType
    headline: str | None
    claimed_source_text: str | None
    vote_overall_verdict: OverallVerdict
    vote_source_status: SourceStatus | None
    vote_content_status: ContentStatus | None
    vote_date_status: DateStatus | None
    ai_overall_verdict: OverallVerdict
    ai_source_status: SourceStatus | None
    ai_content_status: ContentStatus | None
    ai_date_status: DateStatus | None
    final_overall_verdict: OverallVerdict | None
    final_source_status: SourceStatus | None
    final_content_status: ContentStatus | None
    final_date_status: DateStatus | None
    matched: bool | None
    voted_at: datetime


class ExpertStatsResponse(BaseModel):
    user_id: str
    full_name: str | None
    total_votes: int
    correct_votes: int
    accuracy_pct: float | None
    current_credibility: float


class CredibilityScoreResponse(BaseModel):
    user_id: str
    score: float
    total_votes: int
    correct_votes: int
    updated_at: datetime

    model_config = {"from_attributes": True}
