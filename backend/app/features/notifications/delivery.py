"""Recoverable submitter-only result notifications and final-result email.

Reconciliation reads committed results, covering sync, async and reused claims.
No public feed is exposed. SMTP delivery is at-least-once across process crashes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.core.constants import SubmissionStatus
from app.db.engine import AsyncSessionLocal
from app.features.auth.models import User
from app.features.multimodal.models import MultimodalAnalysis
from app.features.notifications.models import Notification, ResultDelivery
from app.features.submissions.models import Submission
from app.features.verification.models import VerificationResult
from app.shared.email_service import EmailService

log = structlog.get_logger(__name__)
READY = (SubmissionStatus.EXPERT_REVIEW, SubmissionStatus.FINALIZED, SubmissionStatus.ESCALATED)


async def reconcile(session, *, limit: int = 100) -> int:
    original = aliased(VerificationResult)
    verdict = func.coalesce(original.overall_verdict, VerificationResult.overall_verdict, MultimodalAnalysis.expert_overall_verdict)
    count = 0
    for stage in ('preliminary', 'final'):
        stmt = (select(Submission, verdict.label('verdict'))
                .outerjoin(VerificationResult, VerificationResult.submission_id == Submission.id)
                .outerjoin(original, original.submission_id == VerificationResult.reused_from_submission_id)
                .outerjoin(MultimodalAnalysis, MultimodalAnalysis.submission_id == Submission.id)
                .where(Submission.submitter_id.is_not(None), Submission.status.in_(READY),
                       or_(VerificationResult.source_status.is_not(None), MultimodalAnalysis.id.is_not(None)),
                       ~exists().where(ResultDelivery.submission_id == Submission.id, ResultDelivery.stage == stage))
                .order_by(Submission.created_at, Submission.id).limit(limit)
                .with_for_update(of=Submission, skip_locked=True))
        if stage == 'final':
            stmt = stmt.where(verdict.is_not(None))
        for submission, final_verdict in (await session.execute(stmt)).all():
            final = stage == 'final'
            label = str(getattr(final_verdict, 'value', final_verdict)).capitalize() if final else None
            title = 'Final result ready' if final else 'Preliminary result ready'
            body = f'Final verdict: {label}. View your result.' if final else 'Your automatic check is complete. View your result.'
            link = f'/verify/{submission.id}'
            kind = 'EXPERT_REVIEW_COMPLETE' if final else 'VERIFICATION_COMPLETE'
            # Existing pipeline notifications use this same identity. A failed
            # insert rolls back the delivery marker, allowing the next retry.
            existing = await session.scalar(select(Notification.id).where(
                Notification.user_id == submission.submitter_id,
                Notification.notification_type == kind, Notification.link_url == link).limit(1))
            if existing is None:
                session.add(Notification(user_id=submission.submitter_id, title=title,
                                         body=body, notification_type=kind, link_url=link, is_read=False))
            session.add(ResultDelivery(submission_id=submission.id, stage=stage,
                                       verdict=label, email_status='pending' if final else 'not_applicable'))
            count += 1
        await session.flush()
    return count


async def deliver_email(session, mailer: EmailService) -> bool:
    """Hold a row lock during delivery so multiple workers cannot send together."""
    now = datetime.now(timezone.utc)
    row = await session.scalar(select(ResultDelivery).where(
        ResultDelivery.email_status == 'pending',
        or_(ResultDelivery.next_attempt_at.is_(None), ResultDelivery.next_attempt_at <= now),
    ).order_by(ResultDelivery.created_at).limit(1).with_for_update(skip_locked=True))
    if row is None:
        return False
    submission = await session.get(Submission, row.submission_id)
    user = await session.get(User, submission.submitter_id) if submission and submission.submitter_id else None
    if user is None or not user.is_active:
        row.email_status = 'skipped'
        return True
    try:
        await mailer.send_result_email(to_email=user.email, submission_id=str(submission.id),
                                       headline=submission.headline or 'Your claim', verdict=row.verdict or 'Complete')
        row.email_status = 'sent'
        row.sent_at = now
    except Exception:
        row.email_attempts += 1
        row.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(row.email_attempts, 7)))
        log.warning('result_email_retry', submission_id=str(row.submission_id), attempt=row.email_attempts)
    await session.flush()
    return True


class ResultDeliveryWorker:
    def __init__(self, session_factory=AsyncSessionLocal):
        self.session_factory = session_factory
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run(), name='result-delivery')

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def run(self):
        mailer = EmailService()
        while True:
            try:
                async with self.session_factory() as session:
                    await reconcile(session)
                    await session.commit()
                if get_settings().email.is_configured:
                    for _ in range(10):
                        async with self.session_factory() as session:
                            sent = await deliver_email(session, mailer)
                            await session.commit()
                        if not sent:
                            break
            except Exception:
                log.exception('result_delivery_retry')
            await asyncio.sleep(15)
