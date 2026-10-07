"""Escalation of undecided claims to admin review: admin notification and the periodic review-limit sweep."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SubmissionStatus
from app.features.auth.models import User
from app.features.expert_review.models import ExpertReview
from app.features.notifications.service import notify_once
from app.features.submissions.models import Submission
from app.shared.utils.headline_preview import headline_preview

log = structlog.get_logger(__name__)

ESCALATION_NOTIFICATION_TYPE = "CLAIM_ESCALATED"
SWEEP_INTERVAL_SECONDS = 60


def admin_review_link(submission_id) -> str:
    return f"/admin/review-queue/{submission_id}"


def escalation_message(headline: str | None) -> str:
    preview = headline_preview(headline) or "Untitled claim"
    return f"Expert reviewers are having difficulty deciding this claim: {preview}"


async def notify_admins_of_escalation(session: AsyncSession, submission: Submission) -> int:
    """One notification per active admin, linking to the claim in the admin
    review queue. `notify_once` keys on (user, type, link), so a retried
    transaction cannot duplicate it either."""
    admin_ids = (
        await session.execute(select(User.id).where(User.role == "admin", User.is_active.is_(True)))
    ).scalars().all()
    sent = 0
    for admin_id in admin_ids:
        sent += await notify_once(
            session,
            user_id=admin_id,
            notification_type=ESCALATION_NOTIFICATION_TYPE,
            link_url=admin_review_link(submission.id),
            title="Admin decision needed",
            body=escalation_message(submission.headline),
        )
    return sent


def _service(session: AsyncSession):
    from app.features.expert_review.repository import (
        CredibilityWeightTierRepository,
        ExpertProfileRepository,
        ExpertReviewRepository,
        VotingConfigRepository,
    )
    from app.features.expert_review.service import ExpertReviewService
    from app.features.multimodal.repository import MultimodalAnalysisRepository
    from app.features.submissions.repository import SubmissionRepository
    from app.features.verification.repository import ResultRepository

    return ExpertReviewService(
        review_repo=ExpertReviewRepository(session),
        profile_repo=ExpertProfileRepository(session),
        tier_repo=CredibilityWeightTierRepository(session),
        submission_repo=SubmissionRepository(session),
        result_repo=ResultRepository(session),
        multimodal_repo=MultimodalAnalysisRepository(session),
        voting_config_repo=VotingConfigRepository(session),
    )


async def sweep_review_limits(
    session: AsyncSession, *, now: datetime | None = None, limit: int = 50
) -> int:
    """Re-evaluates open claims that have exceeded a configured limit. Returns
    how many changed status (finalized or escalated). Caller commits."""
    from app.features.expert_review.repository import VotingConfigRepository

    config = await VotingConfigRepository(session).get_or_create()
    if config.max_review_hours is None and config.max_review_votes is None:
        return 0
    now = now or datetime.now(timezone.utc)

    over_limit = []
    if config.max_review_hours is not None:
        over_limit.append(Submission.created_at <= now - timedelta(hours=config.max_review_hours))
    if config.max_review_votes is not None:
        votes = (
            select(func.count())
            .select_from(ExpertReview)
            .where(ExpertReview.submission_id == Submission.id, ExpertReview.is_admin_decision.is_(False))
            .scalar_subquery()
        )
        over_limit.append(votes >= config.max_review_votes)

    ids = (
        await session.execute(
            select(Submission.id)
            .where(
                Submission.status == SubmissionStatus.EXPERT_REVIEW,
                Submission.duplicate_of_submission_id.is_(None),
                or_(*over_limit),
            )
            .order_by(Submission.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()

    svc = _service(session)
    changed = 0
    for submission_id in ids:
        if await svc.reevaluate(submission_id, now=now):
            changed += 1
    return changed


class EscalationWorker:
    """Runs `sweep_review_limits` every SWEEP_INTERVAL_SECONDS."""

    def __init__(self, session_factory=None, interval_s: float = SWEEP_INTERVAL_SECONDS):
        if session_factory is None:
            from app.db.engine import AsyncSessionLocal

            session_factory = AsyncSessionLocal
        self.session_factory = session_factory
        self.interval_s = interval_s
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self.run(), name="review-escalation")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def run(self) -> None:
        while True:
            try:
                async with self.session_factory() as session:
                    changed = await sweep_review_limits(session)
                    await session.commit()
                if changed:
                    log.info("review_limit_sweep", changed=changed)
            except Exception:
                log.exception("review_limit_sweep_failed")
            await asyncio.sleep(self.interval_s)
