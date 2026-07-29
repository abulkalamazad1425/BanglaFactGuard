from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import VerificationLabel


class ExpertVoteRequest(BaseModel):
    expert_label: VerificationLabel
    justification: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Expert's written justification for the verdict (min 50 characters)",
    )


class ExpertVoteUpdateRequest(BaseModel):
    expert_label: VerificationLabel | None = None
    justification: str | None = Field(default=None, min_length=50, max_length=5000)


class ExpertReviewResponse(BaseModel):
    id: str
    claim_id: str
    reviewer_id: str | None
    ai_label: str
    expert_label: str
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
    claim_id: str
    headline: str | None
    news_body: str | None = None
    claimed_source: str | None
    ai_label: str | None
    ai_confidence: float | None
    submitted_at: datetime
    vote_count: int
    top_article: ExpertTopArticle | None = None


class ExpertHistoryItemResponse(BaseModel):
    review_id: str
    claim_id: str
    headline: str | None
    claimed_source: str | None
    expert_label: str
    ai_label: str
    final_label: str | None
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
