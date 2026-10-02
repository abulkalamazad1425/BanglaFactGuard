from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.core.constants import SubmissionStatus, SubmissionType


class SubmissionLookupResponse(BaseModel):
    """Minimal, type-agnostic submission summary.

    Each verification method (source-based, multimodal, photo-card) has its
    own detail endpoint with its own shape — GET /verify/{id}, GET
    /multimodal/by-submission/{id}, GET /photocard/{id}. A result page that
    only has a submission_id (from Fact Explorer, submission history, or a
    notification link) needs to know which of those to call before it can
    fetch anything, since the three are not interchangeable. This endpoint
    is that first lookup.
    """

    submission_id: uuid.UUID
    submission_type: SubmissionType
    status: SubmissionStatus
    headline: str | None
    body_text: str | None = None
    claimed_source_text: str | None = None
    published_date: date | None = None
    processing_phase: str | None = None
    failure_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
