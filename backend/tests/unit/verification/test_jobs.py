"""Background execution: idempotent job bodies, bounded retries with one
failure notice, restart recovery, and photo cards in their own lane."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.constants import SubmissionStatus, SubmissionType
from app.core.exceptions import PermanentJobError, SourceNotFoundError
from app.features.notifications.models import Notification
from app.features.submissions.models import Submission
from app.features.verification import jobs
from app.features.verification.job_repository import VerificationJobRepository
from app.features.verification.jobs import JobDeps, VerificationJobWorker, execute_job
from tests.helpers.db import add_completed_submission, add_user


def deps(**extra) -> JobDeps:
    return JobDeps(*(MagicMock() for _ in range(5)), **extra)


async def pending(db, *, kind="SOURCE_BASED", submitter_id=None, status="QUEUED", locked_ago=None,
                  queued_at: int = 0) -> uuid.UUID:
    async with db() as s:
        sub = Submission(submission_type=SubmissionType.SOURCE_BASED, headline="h", content_hash=uuid.uuid4().hex,
                         status=SubmissionStatus.PENDING, submitter_id=submitter_id)
        s.add(sub)
        await s.flush()
        job = await VerificationJobRepository(s).enqueue(sub.id, kind)
        job.status = status
        job.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=queued_at)
        if locked_ago is not None:
            job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=locked_ago)
        await s.commit()
        return sub.id


async def job_of(db, sid):
    async with db() as s:
        return await VerificationJobRepository(s).get_by_submission(sid)


async def wait_for(db, sid, status, tries=300):
    for _ in range(tries):
        job = await job_of(db, sid)
        if job.status == status:
            return job
        await asyncio.sleep(0.02)
    return job


# ── execute_job ──────────────────────────────────────────────────────────

async def test_job_bodies_are_idempotent_and_dispatched_by_kind(db, monkeypatch):
    with pytest.raises(PermanentJobError):  # deleted before it ran
        await execute_job(kind="SOURCE_BASED", submission_id=uuid.uuid4(), payload={}, deps=deps(), session_factory=db)
    async with db() as s:
        done, _ = await add_completed_submission(s, headline="h", submitter_id=None)
        await s.commit()
    ran = AsyncMock()
    monkeypatch.setattr(jobs.VerificationService, "run_for_submission", ran)
    await execute_job(kind="SOURCE_BASED", submission_id=done.id, payload={}, deps=deps(), session_factory=db)
    ran.assert_not_awaited()  # already in review: nothing re-runs

    sid = await pending(db)
    await execute_job(kind="SOURCE_BASED", submission_id=sid, payload={}, deps=deps(), session_factory=db)
    ran.assert_awaited_once_with(sid)
    async with db() as s:
        assert (await s.get(Submission, sid)).processing_phase == "VERIFYING"

    card = AsyncMock()
    monkeypatch.setattr(jobs.PhotoCardService, "process_submission", card)
    await execute_job(kind="PHOTO_CARD", submission_id=sid, payload={}, deps=deps(), session_factory=db)
    card.assert_awaited_once_with(sid)


async def test_multimodal_jobs_need_the_model_and_storage(db, monkeypatch):
    from app.features.multimodal.service import MultimodalPredictionService

    sid = await pending(db, kind="MULTIMODAL")
    for extra in ({}, {"multimodal_loader": SimpleNamespace(is_loaded=True)}):
        with pytest.raises(PermanentJobError):
            await execute_job(kind="MULTIMODAL", submission_id=sid, payload={}, deps=deps(**extra), session_factory=db)
    process = AsyncMock()
    monkeypatch.setattr(MultimodalPredictionService, "process_queued", process)
    ready = deps(multimodal_loader=SimpleNamespace(is_loaded=True), multimodal_storage=MagicMock())
    await execute_job(kind="MULTIMODAL", submission_id=sid, payload={"image_key": "k"}, deps=ready, session_factory=db)
    assert process.await_args.args[1] == {"image_key": "k"}


async def test_an_unresolvable_source_is_a_permanent_failure_and_rolls_back(db, monkeypatch):
    sid = await pending(db)
    monkeypatch.setattr(jobs.VerificationService, "run_for_submission",
                        AsyncMock(side_effect=SourceNotFoundError("অজানা")))
    with pytest.raises(PermanentJobError):
        await execute_job(kind="SOURCE_BASED", submission_id=sid, payload={}, deps=deps(), session_factory=db)


# ── the worker ───────────────────────────────────────────────────────────

async def test_a_restarted_worker_recovers_queued_and_crashed_jobs_only(file_db):
    queued = await pending(file_db)
    stranded = await pending(file_db, status="RUNNING", locked_ago=600)
    alive = await pending(file_db, status="RUNNING", locked_ago=1)
    ran = []

    async def runner(**kw):
        ran.append(kw["submission_id"])

    worker = VerificationJobWorker(deps(), session_factory=file_db, stale_after_s=120, poll_interval_s=0.05, runner=runner)
    worker.start()
    worker.start()  # idempotent
    await wait_for(file_db, queued, "DONE")
    await wait_for(file_db, stranded, "DONE")
    await worker.stop()
    assert set(ran) == {queued, stranded} and (await job_of(file_db, alive)).status == "RUNNING"


@pytest.mark.parametrize("error,attempts", [(RuntimeError("boom"), 3), (PermanentJobError("Card unreadable."), 1)])
async def test_failures_retry_boundedly_then_notify_the_owner_once(file_db, error, attempts):
    async with file_db() as s:
        owner = await add_user(s)
        await s.commit()
    sid = await pending(file_db, submitter_id=owner.id)
    calls = []

    async def failing(**kw):
        calls.append(1)
        raise error

    worker = VerificationJobWorker(deps(), session_factory=file_db, poll_interval_s=0.02, runner=failing)
    worker.start()
    job = await wait_for(file_db, sid, "FAILED")
    await worker.stop()
    assert len(calls) == job.attempts == attempts
    async with file_db() as s:
        sub = await s.get(Submission, sid)
        notes = (await s.execute(select(Notification).where(Notification.user_id == owner.id))).scalars().all()
    assert sub.status == SubmissionStatus.FAILED and sub.failure_reason
    if isinstance(error, PermanentJobError):
        assert sub.failure_reason == "Card unreadable."
    assert [n.notification_type for n in notes] == ["VERIFICATION_FAILED"]


async def test_photo_cards_waiting_on_gemini_never_block_text_jobs(file_db):
    cards = [await pending(file_db, kind="PHOTO_CARD", queued_at=i) for i in range(3)]
    text = await pending(file_db, queued_at=10)  # queued after the cards
    release = asyncio.Event()
    done: list[uuid.UUID] = []

    async def runner(**kw):
        if kw["kind"] == "PHOTO_CARD":
            await release.wait()
        done.append(kw["submission_id"])

    worker = VerificationJobWorker(deps(), session_factory=file_db, concurrency=1, photocard_concurrency=1,
                                   poll_interval_s=0.02, runner=runner)
    worker.start()
    assert (await wait_for(file_db, text, "DONE")).status == "DONE" and done == [text]
    release.set()
    for sid in cards:
        assert (await wait_for(file_db, sid, "DONE")).status == "DONE"
    await worker.stop()


def test_dependencies_come_from_the_app_state():
    state = SimpleNamespace(cache_service=1, embedding_service=2, ner_service=3, nli_service=4, http_client=5,
                            photocard_storage=6)
    d = JobDeps.from_app_state(state)
    assert (d.cache_service, d.http_client, d.photocard_storage, d.multimodal_loader) == (1, 5, 6, None)
