

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import OverallVerdict, SubmissionStatus, SubmissionType
from app.features.auth.models import User
from app.features.expert_review.models import ExpertReview
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult


class PublicVote(BaseModel):
    reviewer_name: str
    reviewer_role: str = Field(description="Expert | Admin")
    overall_vote: OverallVerdict
    justification: str | None
    voted_at: datetime
    is_final_decision: bool = Field(
        default=False, description="True for the administrator's final decision on an escalated claim."
    )


class PublicVotingDetails(BaseModel):
    submission_id: uuid.UUID
    final_verdict: OverallVerdict
    decided_by: str = Field(description="EXPERT_CONSENSUS | ADMIN")
    finalized_at: datetime | None = None
    votes: list[PublicVote]


async def _final_verdict(session: AsyncSession, origin: Submission):
    if origin.submission_type == SubmissionType.MULTIMODAL:
        mm = (
            await session.execute(select(MultimodalAnalysis).where(MultimodalAnalysis.submission_id == origin.id))
        ).scalar_one_or_none()
        return (mm.expert_overall_verdict, mm.finalized_at) if mm else (None, None)
    result = (
        await session.execute(select(VerificationResult).where(VerificationResult.submission_id == origin.id))
    ).scalar_one_or_none()
    return (result.overall_verdict, result.finalized_at) if result else (None, None)


async def load_public_voting_details(
    session: AsyncSession, submission: Submission
) -> PublicVotingDetails | None:
    """None unless the claim (or, for a reused copy, the original it reads its
    review from) has a final decision."""
    origin = submission
    if submission.duplicate_of_submission_id:
        origin = await session.get(Submission, submission.duplicate_of_submission_id) or submission
    if origin.status != SubmissionStatus.FINALIZED:
        return None
    verdict, finalized_at = await _final_verdict(session, origin)
    if verdict is None:
        return None

    rows = (
        await session.execute(
            select(ExpertReview, User)
            .outerjoin(User, User.id == ExpertReview.reviewer_id)
            .where(ExpertReview.submission_id == origin.id)
            .order_by(ExpertReview.is_admin_decision.asc(), ExpertReview.created_at.asc())
        )
    ).all()
    votes: list[PublicVote] = []
    expert_n = 0
    for review, user in rows:
        is_admin = bool(review.is_admin_decision)
        if not is_admin:
            expert_n += 1
        fallback = "Administrator" if is_admin else f"Expert reviewer {expert_n}"
        votes.append(
            PublicVote(
                reviewer_name=(user.full_name.strip() if user and user.full_name and user.full_name.strip() else fallback),
                reviewer_role="Admin" if is_admin else "Expert",
                overall_vote=review.vote_overall_verdict,
                justification=review.justification,
                voted_at=review.created_at,
                is_final_decision=is_admin,
            )
        )
    return PublicVotingDetails(
        submission_id=submission.id,
        final_verdict=verdict,
        decided_by="ADMIN" if any(v.is_final_decision for v in votes) else "EXPERT_CONSENSUS",
        finalized_at=finalized_at,
        votes=votes,
    )
