from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CreateExpertRequest(BaseModel):
    full_name: str = Field(..., max_length=255)
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Initial password set by admin. Expert can change it later.",
    )
    expertise_area: str | None = Field(default=None, max_length=255)


class UpdateExpertRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    expertise_area: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class ResetExpertPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=128)


class ExpertResponse(BaseModel):
    id: str
    full_name: str | None
    email: str
    role: str
    is_active: bool
    expertise_area: str | None
    credibility_score: float | None
    total_votes: int

    model_config = {"from_attributes": True}


class VerdictBreakdown(BaseModel):
    """Counts across the 3 independent verdict dimensions.

    Not a single TRUE/FALSE/PARTIALLY_TRUE/NOT_FOUND tally — source, content
    and date are checked independently, so each gets its own pair of counts.
    content_* and date_* only count submissions where that dimension was
    actually evaluated (source CONFIRMED, and — for date — both a claimed and
    an actual publication date known).
    """

    source_confirmed_count: int
    source_not_found_count: int
    content_matched_count: int
    content_altered_count: int
    date_matched_count: int
    date_mismatched_count: int


class AdminStatsResponse(BaseModel):
    total_submissions: int
    submissions_last_30_days: int
    verdict_breakdown: VerdictBreakdown
    pending_expert_reviews: int
    total_experts: int
    active_experts: int
    avg_verification_time_seconds: float | None


class CredibilityWeightTierRequest(BaseModel):
    label: str = Field(..., max_length=100)
    min_accuracy_pct: float = Field(..., ge=0.0, le=100.0)
    max_accuracy_pct: float = Field(..., ge=0.0, le=100.0)
    weight: float = Field(..., gt=0.0)
    is_active: bool = Field(default=True)


class CredibilityWeightTierUpdateRequest(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    min_accuracy_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_accuracy_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    weight: float | None = Field(default=None, gt=0.0)
    is_active: bool | None = None


class CredibilityWeightTierResponse(BaseModel):
    id: str
    label: str
    min_accuracy_pct: float
    max_accuracy_pct: float
    weight: float
    is_active: bool

    model_config = {"from_attributes": True}


class VotingConfigUpdateRequest(BaseModel):
    """All fields optional — PUT applies only the ones provided, leaving the
    rest at their current value (partial update)."""

    min_expert_votes: int | None = Field(
        default=None, ge=1, le=50, description="M — minimum votes before a claim can finalize"
    )
    activation_threshold_votes: int | None = Field(
        default=None,
        ge=0,
        le=1000,
        description="N — lifetime votes an expert needs before their tier weight applies",
    )
    verified_threshold: float | None = Field(
        default=None, gt=0, description="T — weighted score the leading verdict must reach"
    )
    lead_margin: float | None = Field(
        default=None, ge=0, description="Leader's score must exceed the runner-up's by this much"
    )
    max_review_votes: int | None = Field(
        default=None,
        ge=1,
        description="Escalate after this many votes without consensus (omit for no cap)",
    )
    max_review_hours: int | None = Field(
        default=None,
        ge=1,
        description="Escalate after this many hours without consensus (omit for no cap)",
    )
    max_tier_weight: float | None = Field(
        default=None, gt=0, description="Upper bound on any credibility tier's weight"
    )




class VotingConfigResponse(BaseModel):
    id: str
    min_expert_votes: int
    activation_threshold_votes: int
    verified_threshold: float
    lead_margin: float
    max_review_votes: int | None
    max_review_hours: int | None
    max_tier_weight: float | None
    updated_at: datetime

    model_config = {"from_attributes": True}
