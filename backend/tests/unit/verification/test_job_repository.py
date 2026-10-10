"""The durable queue: one job per submission, oldest first, crashed jobs
reclaimed after a stale heartbeat, bounded retries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.constants import SubmissionStatus, SubmissionType
from app.features.submissions.models import Submission
from app.features.verification.job_repository import VerificationJobRepository

_created = iter(range(1000))


async def enqueue(session, kind="SOURCE_BASED", *, status=None, locked_ago=None):
    sub = Submission(submission_type=SubmissionType.SOURCE_BASED, content_hash=uuid.uuid4().hex,
                     status=SubmissionStatus.PENDING)
    session.add(sub)
    await session.flush()
    job = await VerificationJobRepository(session).enqueue(sub.id, kind, payload={"k": 1})
    job.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=next(_created))  # queue order
    if status:
        job.status = status
    if locked_ago is not None:
        job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=locked_ago)
    await session.flush()
    return job


async def test_enqueue_is_idempotent_per_submission(session):
    job = await enqueue(session)
    repo = VerificationJobRepository(session)
    assert await repo.enqueue(job.submission_id, "PHOTO_CARD") is job
    assert (job.status, job.kind, job.payload, job.attempts) == ("QUEUED", "SOURCE_BASED", {"k": 1}, 0)


async def test_claims_follow_lanes_and_reclaim_only_stale_running_jobs(session):
    repo = VerificationJobRepository(session)
    alive = await enqueue(session, status="RUNNING", locked_ago=1)
    card = await enqueue(session, "PHOTO_CARD")
    stranded = await enqueue(session, status="RUNNING", locked_ago=600)
    text = await enqueue(session)

    assert (await repo.claim_next("w", stale_after_s=120, kinds=("PHOTO_CARD",))).id == card.id
    first = await repo.claim_next("w" * 100, stale_after_s=120, exclude_kinds=("PHOTO_CARD",))
    assert first.id == stranded.id and first.attempts == 1 and len(first.locked_by) == 64
    assert (await repo.claim_next("w", stale_after_s=120)).id == text.id
    assert await repo.claim_next("w", stale_after_s=120) is None  # `alive` is still heartbeating
    assert alive.status == "RUNNING"


async def test_retries_are_bounded_and_permanent_errors_fail_at_once(session):
    repo = VerificationJobRepository(session)
    job = await enqueue(session)
    for attempt in (1, 2):
        await repo.claim_next("w", stale_after_s=120)
        assert await repo.release_or_fail(job.id, "boom", permanent=False) is False
        assert (job.status, job.attempts, job.locked_at) == ("QUEUED", attempt, None)
    await repo.claim_next("w", stale_after_s=120)
    assert await repo.release_or_fail(job.id, "boom", permanent=False) is True
    assert job.status == "FAILED" and job.finished_at and job.last_error == "boom"

    other = await enqueue(session)
    assert await repo.release_or_fail(other.id, "no source", permanent=True) is True
    assert await repo.release_or_fail(uuid.uuid4(), "gone", permanent=False) is True


async def test_done_and_heartbeat(session):
    repo = VerificationJobRepository(session)
    job = await enqueue(session, status="RUNNING", locked_ago=600)
    await repo.heartbeat(job.id)
    await session.refresh(job)
    assert (await repo.claim_next("w", stale_after_s=120)) is None  # fresh heartbeat: not reclaimed
    await repo.mark_done(job.id)
    await session.refresh(job)
    assert (job.status, job.locked_at) == ("DONE", None) and job.finished_at
