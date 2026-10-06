from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.verification.models import VerificationJob


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VerificationJobRepository:
    """Queue operations for `verification_jobs`.

    `claim_next` uses ``FOR UPDATE SKIP LOCKED`` so several workers (or
    processes) never take the same job, and treats a RUNNING job whose
    ``locked_at`` is older than ``stale_after`` as abandoned — that is how work
    interrupted by a crash or restart is recovered.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_submission(self, submission_id: uuid.UUID) -> VerificationJob | None:
        return (
            await self.session.execute(
                select(VerificationJob).where(VerificationJob.submission_id == submission_id)
            )
        ).scalar_one_or_none()

    async def enqueue(
        self, submission_id: uuid.UUID, kind: str, *, payload: dict | None = None
    ) -> VerificationJob:
        """Idempotent: one job per submission."""
        existing = await self.get_by_submission(submission_id)
        if existing is not None:
            return existing
        job = VerificationJob(
            submission_id=submission_id,
            kind=kind,
            status="QUEUED",
            attempts=0,
            max_attempts=3,
            payload=payload or {},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def claim_next(
        self,
        worker_id: str,
        *,
        stale_after_s: float,
        kinds: tuple[str, ...] | None = None,
        exclude_kinds: tuple[str, ...] | None = None,
    ) -> VerificationJob | None:
        """The oldest claimable job, optionally restricted to (or excluding)
        some job kinds - the worker runs one lane per kind group."""
        cutoff = _now() - timedelta(seconds=stale_after_s)
        conditions = [
            or_(
                VerificationJob.status == "QUEUED",
                and_(
                    VerificationJob.status == "RUNNING",
                    VerificationJob.locked_at < cutoff,
                ),
            )
        ]
        if kinds:
            conditions.append(VerificationJob.kind.in_(kinds))
        if exclude_kinds:
            conditions.append(VerificationJob.kind.not_in(exclude_kinds))
        stmt = (
            select(VerificationJob)
            .where(*conditions)
            .order_by(VerificationJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await self.session.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        job.status = "RUNNING"
        job.attempts = (job.attempts or 0) + 1
        job.locked_at = _now()
        job.locked_by = worker_id[:64]
        await self.session.flush()
        return job

    async def heartbeat(self, job_id: uuid.UUID) -> None:
        await self.session.execute(
            update(VerificationJob).where(VerificationJob.id == job_id).values(locked_at=_now())
        )

    async def mark_done(self, job_id: uuid.UUID) -> None:
        await self.session.execute(
            update(VerificationJob)
            .where(VerificationJob.id == job_id)
            .values(status="DONE", finished_at=_now(), locked_at=None, last_error=None)
        )

    async def release_or_fail(
        self, job_id: uuid.UUID, error: str, *, permanent: bool
    ) -> bool:
        """Retry (back to QUEUED) unless permanent or out of attempts.
        Returns True when the job is now terminally FAILED."""
        job = (
            await self.session.execute(
                select(VerificationJob).where(VerificationJob.id == job_id).with_for_update()
            )
        ).scalar_one_or_none()
        if job is None:
            return True
        terminal = permanent or (job.attempts or 0) >= (job.max_attempts or 1)
        job.status = "FAILED" if terminal else "QUEUED"
        job.last_error = error[:2000]
        job.locked_at = None
        job.locked_by = None
        if terminal:
            job.finished_at = _now()
        await self.session.flush()
        return terminal
