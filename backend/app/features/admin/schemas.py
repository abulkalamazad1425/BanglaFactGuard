"""
app/features/admin/schemas.py
================================
Pydantic schemas for the admin panel API.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Expert Management
# ---------------------------------------------------------------------------

class CreateExpertRequest(BaseModel):
    """Admin creates a new expert account and sets credentials."""
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
    """Admin updates expert profile info (not credentials)."""
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    expertise_area: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class ResetExpertPasswordRequest(BaseModel):
    """Admin force-resets an expert's password."""
    new_password: str = Field(..., min_length=8, max_length=128)


class ExpertResponse(BaseModel):
    """Expert account info returned to admin."""
    id: str
    full_name: str | None
    email: str
    role: str
    is_active: bool
    expertise_area: str | None
    credibility_score: float | None
    total_votes: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Platform Statistics
# ---------------------------------------------------------------------------

class VerdictBreakdown(BaseModel):
    true_count: int
    false_count: int
    partially_true_count: int
    not_found_count: int


class AdminStatsResponse(BaseModel):
    """Platform-wide metrics for the admin dashboard."""
    total_submissions: int
    submissions_last_30_days: int
    verdict_breakdown: VerdictBreakdown
    pending_expert_reviews: int
    total_experts: int
    active_experts: int
    avg_verification_time_seconds: float | None
