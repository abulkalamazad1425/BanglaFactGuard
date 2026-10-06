"""Admin home page data: what needs action now, what changed, who is active."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus, SubmissionType
from app.features.admin.schemas import (
    AdminDashboardResponse,
    DashboardActivity,
    DashboardClaim,
    DashboardExpert,
)
from app.features.auth.models import User
from app.features.expert_review.models import ExpertProfile, ExpertReview
from app.features.multimodal.models import MultimodalAnalysis
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult

_LIST_SIZE = 8


def _review_count(admin: bool):
    return (
        select(func.count())
        .select_from(ExpertReview)
        .where(ExpertReview.submission_id == Submission.id, ExpertReview.is_admin_decision.is_(admin))
        .correlate(Submission)
        .scalar_subquery()
    )


async def _count(session: AsyncSession, *conditions) -> int:
    return (await session.execute(select(func.count()).select_from(Submission).where(*conditions))).scalar_one()


async def build_admin_dashboard(session: AsyncSession) -> AdminDashboardResponse:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    verdict = case(
        (Submission.submission_type == SubmissionType.MULTIMODAL, MultimodalAnalysis.expert_overall_verdict),
        else_=VerificationResult.overall_verdict,
    )
    finalized_at = func.coalesce(VerificationResult.finalized_at, MultimodalAnalysis.finalized_at)
    base = (
        select(
            Submission,
            _review_count(False).label("votes"),
            verdict.label("verdict"),
            finalized_at.label("finalized_at"),
            _review_count(True).label("admin"),
        )
        .outerjoin(VerificationResult, VerificationResult.submission_id == Submission.id)
        .outerjoin(MultimodalAnalysis, MultimodalAnalysis.submission_id == Submission.id)
        .where(Submission.duplicate_of_submission_id.is_(None))
    )

    async def claims(stmt) -> list[DashboardClaim]:
        rows = (await session.execute(stmt.limit(_LIST_SIZE))).all()
        return [
            DashboardClaim(
                submission_id=str(sub.id),
                headline=sub.headline,
                submission_type=sub.submission_type.value,
                status=sub.status.value,
                vote_count=votes or 0,
                submitted_at=sub.created_at,
                escalated_at=sub.escalated_at,
                final_verdict=getattr(v, "value", v),
                decided_by_admin=bool(admin),
                finalized_at=fin,
            )
            for sub, votes, v, fin, admin in rows
        ]

    last_vote = (
        select(ExpertReview.reviewer_id, func.max(ExpertReview.created_at).label("last_vote"))
        .group_by(ExpertReview.reviewer_id)
        .subquery()
    )
    expert_rows = (
        await session.execute(
            select(User, ExpertProfile.total_votes, last_vote.c.last_vote)
            .outerjoin(ExpertProfile, ExpertProfile.user_id == User.id)
            .outerjoin(last_vote, last_vote.c.reviewer_id == User.id)
            .where(User.role == "expert")
            .order_by(User.is_active.desc(), last_vote.c.last_vote.desc().nulls_last(), User.full_name.asc())
            .limit(12)
        )
    ).all()
    activity_rows = (
        await session.execute(
            select(ExpertReview, User.full_name, Submission.headline)
            .outerjoin(User, User.id == ExpertReview.reviewer_id)
            .join(Submission, Submission.id == ExpertReview.submission_id)
            .order_by(ExpertReview.created_at.desc())
            .limit(10)
        )
    ).all()

    async def experts_with(active: bool) -> int:
        return (
            await session.execute(
                select(func.count()).select_from(User).where(User.role == "expert", User.is_active.is_(active))
            )
        ).scalar_one()

    finalized_week = (
        await session.execute(
            select(func.count())
            .select_from(Submission)
            .outerjoin(VerificationResult, VerificationResult.submission_id == Submission.id)
            .outerjoin(MultimodalAnalysis, MultimodalAnalysis.submission_id == Submission.id)
            .where(Submission.status == SubmissionStatus.FINALIZED, finalized_at >= week_ago)
        )
    ).scalar_one()
    original = Submission.duplicate_of_submission_id.is_(None)

    return AdminDashboardResponse(
        escalated_count=await _count(session, Submission.status == SubmissionStatus.ESCALATED, original),
        pending_review_count=await _count(session, Submission.status == SubmissionStatus.EXPERT_REVIEW, original),
        processing_count=await _count(
            session, Submission.status.in_((SubmissionStatus.PENDING, SubmissionStatus.PROCESSING))
        ),
        failed_last_7_days=await _count(
            session, Submission.status == SubmissionStatus.FAILED, Submission.updated_at >= week_ago
        ),
        submissions_last_7_days=await _count(session, Submission.created_at >= week_ago),
        finalized_last_7_days=finalized_week,
        total_submissions=await _count(session),
        active_experts=await experts_with(True),
        inactive_experts=await experts_with(False),
        escalated_claims=await claims(
            base.where(Submission.status == SubmissionStatus.ESCALATED).order_by(Submission.escalated_at.asc())
        ),
        oldest_pending_reviews=await claims(
            base.where(Submission.status == SubmissionStatus.EXPERT_REVIEW).order_by(Submission.created_at.asc())
        ),
        recent_submissions=await claims(base.order_by(Submission.created_at.desc())),
        recent_decisions=await claims(
            base.where(Submission.status == SubmissionStatus.FINALIZED).order_by(finalized_at.desc().nulls_last())
        ),
        experts=[
            DashboardExpert(
                id=str(u.id), full_name=u.full_name, is_active=u.is_active,
                total_votes=total_votes or 0, last_vote_at=last,
            )
            for u, total_votes, last in expert_rows
        ],
        recent_activity=[
            DashboardActivity(
                kind="ADMIN_DECISION" if r.is_admin_decision else "VOTE",
                actor=name or ("Administrator" if r.is_admin_decision else "Expert"),
                submission_id=str(r.submission_id),
                headline=headline,
                overall_vote=r.vote_overall_verdict.value,
                at=r.created_at,
            )
            for r, name, headline in activity_rows
        ],
    )
