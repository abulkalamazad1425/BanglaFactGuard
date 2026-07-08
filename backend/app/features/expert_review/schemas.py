"""
app/features/expert_review/schemas.py
========================================
Pydantic schemas for the expert review feature.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import VerificationLabel


class ExpertVoteRequest(BaseModel):
    """Request body for POST /api/v1/expert/queue/{claim_id}/vote."""
    expert_label: VerificationLabel
    justification: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Expert's written justification for the verdict (min 50 characters)",
    )


class ExpertVoteUpdateRequest(BaseModel):
    """Request body for PUT /api/v1/expert/reviews/{review_id}."""
    expert_label: VerificationLabel | None = None
    justification: str | None = Field(default=None, min_length=50, max_length=5000)


class ExpertReviewResponse(BaseModel):
    """Full review record returned to the expert."""
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
    """Top matched article for queue preview."""
    url: str
    title: str | None = None
    published_date: str | None = None
    rank_score: float | None = None
    body_snippet: str | None = None  # First 400 chars


class ExpertQueueItemResponse(BaseModel):
    """Summary of a claim awaiting expert review."""
    claim_id: str
    headline: str | None
    news_body: str | None = None       # Submitted news body (truncated preview)
    claimed_source: str | None
    ai_label: str | None
    ai_confidence: float | None
    submitted_at: datetime
    vote_count: int  # how many experts have voted so far
    top_article: ExpertTopArticle | None = None  # Highest-ranked matched article


class ExpertHistoryItemResponse(BaseModel):
    """A single item in an expert's vote history."""
    review_id: str
    claim_id: str
    headline: str | None
    claimed_source: str | None
    expert_label: str
    ai_label: str
    final_label: str | None  # None if not yet finalized
    matched: bool | None      # True if expert_label == final_label
    voted_at: datetime


class ExpertStatsResponse(BaseModel):
    """Aggregate performance stats for an expert."""
    user_id: str
    full_name: str | None
    total_votes: int
    correct_votes: int
    accuracy_pct: float | None  # None if total_votes == 0
    current_credibility: float


class CredibilityScoreResponse(BaseModel):
    """Credibility score record."""
    user_id: str
    score: float
    total_votes: int
    correct_votes: int
    updated_at: datetime

    model_config = {"from_attributes": True}
