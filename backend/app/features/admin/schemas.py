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


class AdminStatsResponse(BaseModel):
    total_submissions: int
    submissions_last_30_days: int
    pending_expert_reviews: int = Field(description="Claims currently open for expert voting.")
    escalated_claims: int = Field(default=0, description="Claims awaiting an admin decision.")
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
        description=(
            "N — votes on claims whose final decision is complete that an expert "
            "needs before their accuracy-based tier weight applies"
        ),
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
        description=(
            "Escalate to admin once this many votes are cast without a final "
            "decision (null = not configured). Either limit being exceeded escalates."
        ),
    )
    max_review_hours: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Escalate to admin once this many hours have passed since submission "
            "without a final decision (null = not configured). Enforced by a "
            "background sweep, independent of new votes or page visits."
        ),
    )




class VotingConfigResponse(BaseModel):
    id: str
    min_expert_votes: int
    activation_threshold_votes: int
    verified_threshold: float
    lead_margin: float
    max_review_votes: int | None
    max_review_hours: int | None
    updated_at: datetime

    model_config = {"from_attributes": True}



class DashboardClaim(BaseModel):
    submission_id: str
    headline: str | None
    submission_type: str
    status: str
    vote_count: int = 0
    submitted_at: datetime
    escalated_at: datetime | None = None
    final_verdict: str | None = None
    decided_by_admin: bool = False
    finalized_at: datetime | None = None


class DashboardExpert(BaseModel):
    id: str
    full_name: str | None
    is_active: bool
    total_votes: int
    last_vote_at: datetime | None = None


class DashboardActivity(BaseModel):
    kind: str = Field(description="VOTE | ADMIN_DECISION")
    actor: str
    submission_id: str
    headline: str | None
    overall_vote: str
    at: datetime


class AdminDashboardResponse(BaseModel):
    """Everything the admin home page needs in one call: what needs action
    (escalated claims, open reviews), what changed recently and who is active."""

    escalated_count: int
    pending_review_count: int
    processing_count: int
    failed_last_7_days: int
    submissions_last_7_days: int
    finalized_last_7_days: int
    total_submissions: int
    active_experts: int
    inactive_experts: int
    escalated_claims: list[DashboardClaim]
    oldest_pending_reviews: list[DashboardClaim]
    recent_submissions: list[DashboardClaim]
    recent_decisions: list[DashboardClaim]
    experts: list[DashboardExpert]
    recent_activity: list[DashboardActivity]
