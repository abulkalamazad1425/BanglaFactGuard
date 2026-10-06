from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.core.constants import (
    ContentStatus,
    DateStatus,
    HeadlineAlterationStatus,
    HeadlineCheckStatus,
    OverallVerdict,
    SourceStatus,
    SubmissionStatus,
    SubmissionType,
)
from app.features.verification.schemas import BodySimilarityReport, HeadlineAlterationDetail


class ExpertVoteRequest(BaseModel):
    """A reviewer's vote. `overall_verdict` ("Cast your vote based on your
    findings": Real / Fake / Misleading / Altered) is mandatory for every
    submission type and is the ONLY input to the final decision, consensus
    and escalation. source/content/date are optional supplementary findings
    for SOURCE_BASED/PHOTO_CARD claims, recorded for reference only; the
    validator just keeps them internally consistent (headline/date findings
    only when the relevant article was found)."""

    overall_verdict: OverallVerdict
    source_status: SourceStatus | None = None
    content_status: ContentStatus | None = None
    date_status: DateStatus | None = None
    justification: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Reviewer's written justification for the vote (min 50 characters). Shown publicly after the final decision.",
    )

    @model_validator(mode="after")
    def _check_conditional_fields(self) -> "ExpertVoteRequest":
        if self.source_status != SourceStatus.CONFIRMED and (
            self.content_status is not None or self.date_status is not None
        ):
            raise ValueError(
                "content_status and date_status only apply when source_status is CONFIRMED"
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
    ai_overall_verdict: OverallVerdict | None = Field(
        default=None,
        description="MULTIMODAL only — automated checks never produce an Overall verdict otherwise.",
    )
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
    is_admin_decision: bool = False
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
    status: SubmissionStatus | None = None
    escalated_at: datetime | None = None
    published_date: date | None = Field(
        default=None, description="The publication date the submitter claimed, if any."
    )
    has_voted: bool = False
    can_vote: bool = Field(
        default=False,
        description=(
            "Whether the requesting reviewer may vote now: experts on open claims "
            "they did not submit or vote on; admins only on ESCALATED claims."
        ),
    )
    decision_mode: str = Field(
        default="EXPERT_VOTE",
        description="EXPERT_VOTE, or ADMIN_FINAL when an admin's vote will be the final decision.",
    )
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
    headline_status: HeadlineAlterationStatus | None = None
    date_status: DateStatus | None = None
    ai_confidence: float | None
    submitted_at: datetime
    vote_count: int
    top_article: ExpertTopArticle | None = None
    image_url: str | None = Field(
        default=None, description="Multimodal submissions only — the submitted card/photo"
    )
    headline_check_status: HeadlineCheckStatus | None = Field(
        default=None,
        description="Processing status of the Headline Alteration check (why content_status may be null).",
    )
    headline_alteration: HeadlineAlterationDetail | None = Field(
        default=None,
        description="Headline Alteration detail (claim headline vs. source title only).",
    )
    body_similarity: BodySimilarityReport | None = Field(
        default=None,
        description="Claim body vs. source body similarity measurements - never a verdict.",
    )


class ExpertHistoryItemResponse(BaseModel):
    review_id: str
    submission_id: str
    submission_type: SubmissionType
    submission_status: SubmissionStatus | None = None
    headline: str | None
    claimed_source_text: str | None
    vote_overall_verdict: OverallVerdict
    vote_source_status: SourceStatus | None
    vote_content_status: ContentStatus | None
    vote_date_status: DateStatus | None
    ai_overall_verdict: OverallVerdict | None
    ai_source_status: SourceStatus | None
    ai_content_status: ContentStatus | None
    ai_date_status: DateStatus | None
    final_overall_verdict: OverallVerdict | None
    # Deprecated: the final decision is the overall verdict only. Kept for
    # response compatibility; always null.
    final_source_status: SourceStatus | None = None
    final_content_status: ContentStatus | None = None
    final_date_status: DateStatus | None = None
    matched: bool | None
    is_admin_decision: bool = False
    voted_at: datetime


class ExpertStatsResponse(BaseModel):
    user_id: str
    full_name: str | None
    total_votes: int
    correct_votes: int
    accuracy_pct: float | None
    current_credibility: float | None
    activation_threshold: int = 10


class CredibilityScoreResponse(BaseModel):
    user_id: str
    score: float | None
    total_votes: int
    correct_votes: int
    updated_at: datetime

    model_config = {"from_attributes": True}
