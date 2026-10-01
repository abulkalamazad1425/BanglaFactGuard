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
    min_expert_votes: int = Field(
        ...,
        ge=1,
        le=50,
        description="Number of expert votes required on a claim before it is finalized",
    )


class VotingConfigResponse(BaseModel):
    id: str
    min_expert_votes: int
    updated_at: datetime

    model_config = {"from_attributes": True}
