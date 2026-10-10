"""Time/vote-limit escalation does not wait for a vote: the periodic sweep
escalates once, and every active admin is told exactly once."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.constants import SubmissionStatus
from app.features.expert_review import escalation
from app.features.expert_review.escalation import (
    EscalationWorker,
    escalation_message,
    notify_admins_of_escalation,
    sweep_review_limits,
)
from app.features.notifications.models import Notification
from tests.helpers.db import add_completed_submission, add_user, add_voting_config

HEADLINE = "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা, অফিসগামীদের চরম দুর্ভোগ"


async def claim(session, age_hours: float):
    sub, _ = await add_completed_submission(session, headline=HEADLINE, submitter_id=None)
    sub.created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    await session.flush()
    return sub


async def test_the_time_limit_escalates_once_without_any_vote(session):
    await add_voting_config(session, max_review_hours=24)
    admin = await add_user(session, role="admin")
    await add_user(session, role="admin", is_active=False)  # inactive admins are not notified
    old, fresh = await claim(session, 25), await claim(session, 23)
    assert await sweep_review_limits(session) == 1 and await sweep_review_limits(session) == 0
    assert (old.status, fresh.status) == (SubmissionStatus.ESCALATED, SubmissionStatus.EXPERT_REVIEW)
    note = (await session.execute(select(Notification))).scalar_one()
    assert (note.user_id, note.link_url) == (admin.id, f"/admin/review-queue/{old.id}")
    assert note.body == "Expert reviewers are having difficulty deciding this claim: ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা,..."
    assert await notify_admins_of_escalation(session, old) == 0  # a retry never duplicates it


async def test_without_configured_limits_nothing_is_ever_escalated(session):
    await add_voting_config(session)
    sub = await claim(session, 10_000)
    assert await sweep_review_limits(session) == 0 and sub.status == SubmissionStatus.EXPERT_REVIEW
    assert escalation_message(None) == "Expert reviewers are having difficulty deciding this claim: Untitled claim"


async def test_the_worker_sweeps_periodically_and_survives_errors(db, monkeypatch):
    sweeps = AsyncMock(side_effect=[2, RuntimeError("db down")])
    monkeypatch.setattr(escalation, "sweep_review_limits", sweeps)
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(escalation.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await EscalationWorker(db, interval_s=7).run()
    assert sweeps.await_count == 2 and sleeps == [7, 7]

    worker = EscalationWorker(db)
    await worker.stop()
    monkeypatch.setattr(EscalationWorker, "run", lambda self: asyncio.sleep(3600))
    worker.start()
    await worker.stop()
    assert worker.task.cancelled() and EscalationWorker().session_factory is not None
