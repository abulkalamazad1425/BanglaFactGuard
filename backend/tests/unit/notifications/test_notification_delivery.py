"""Submitter-only result notices (preliminary and final, once each) and the
final-result email, retried with backoff and never duplicated."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.constants import OverallVerdict, SubmissionStatus, SubmissionType
from app.features.notifications import delivery
from app.features.notifications.delivery import ResultDeliveryWorker, deliver_email, reconcile
from app.features.notifications.models import Notification, ResultDelivery
from tests.helpers.db import add_completed_submission, add_multimodal_submission, add_user


async def notices(session) -> list[Notification]:
    return (await session.scalars(select(Notification))).all()


@pytest.mark.parametrize("kind", list(SubmissionType))
async def test_each_stage_is_notified_once_and_the_final_one_is_emailed(session, kind):
    user = await add_user(session)
    if kind == SubmissionType.MULTIMODAL:
        sub, result = await add_multimodal_submission(session, submitter_id=user.id)
    else:
        sub, result = await add_completed_submission(session, headline="A claim", submitter_id=user.id, submission_type=kind)
    assert await reconcile(session) == 1 and await reconcile(session) == 0
    sub.status = SubmissionStatus.FINALIZED
    if kind == SubmissionType.MULTIMODAL:
        result.expert_overall_verdict = OverallVerdict.REAL
    else:
        result.overall_verdict = OverallVerdict.REAL
    await session.flush()
    assert await reconcile(session) == 1 and await reconcile(session) == 0
    rows = await notices(session)
    assert sorted(n.notification_type for n in rows) == ["EXPERT_REVIEW_COMPLETE", "VERIFICATION_COMPLETE"]
    assert all(n.user_id == user.id and n.link_url == f"/verify/{sub.id}" for n in rows)

    mail = AsyncMock()
    assert await deliver_email(session, mail) and not await deliver_email(session, mail)
    kwargs = mail.send_result_email.await_args.kwargs
    assert (kwargs["to_email"], kwargs["verdict"]) == (user.email, "Real")


async def test_guests_get_nothing_and_a_reused_copy_follows_its_original(session):
    await add_completed_submission(session, headline="Guest", submitter_id=None, overall_verdict=OverallVerdict.FAKE)
    assert await reconcile(session) == 0
    user = await add_user(session)
    original, result = await add_completed_submission(session, headline="Original", submitter_id=None)
    copy, _ = await add_completed_submission(session, headline="Original", submitter_id=user.id,
                                             reused_from_submission_id=original.id)
    copy.duplicate_of_submission_id = original.id
    await session.flush()
    assert await reconcile(session) == 1  # preliminary only
    original.status, result.overall_verdict = SubmissionStatus.FINALIZED, OverallVerdict.ALTERED
    await session.flush()
    assert await reconcile(session) == 1
    mail = AsyncMock()
    await deliver_email(session, mail)
    assert mail.send_result_email.await_args.kwargs["submission_id"] == str(copy.id)
    assert mail.send_result_email.await_args.kwargs["verdict"] == "Altered"


async def test_smtp_failures_back_off_and_retry_without_new_notices(session):
    user = await add_user(session)
    sub, _ = await add_completed_submission(session, headline="Final", submitter_id=user.id, overall_verdict=OverallVerdict.FAKE)
    await reconcile(session)
    mail = AsyncMock()
    mail.send_result_email.side_effect = RuntimeError("SMTP offline")
    assert await deliver_email(session, mail)
    row = await session.get(ResultDelivery, (sub.id, "final"))
    assert (row.email_status, row.email_attempts) == ("pending", 1) and row.next_attempt_at
    assert not await deliver_email(session, mail)  # waiting out the backoff
    row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    mail.send_result_email.side_effect = None
    assert await deliver_email(session, mail) and row.email_status == "sent"
    assert await reconcile(session) == 0 and len(await notices(session)) == 2


async def test_an_inactive_account_is_skipped(session):
    user = await add_user(session)
    await add_completed_submission(session, headline="Final", submitter_id=user.id, overall_verdict=OverallVerdict.FAKE)
    await reconcile(session)
    user.is_active = False
    mail = AsyncMock()
    assert await deliver_email(session, mail)
    mail.send_result_email.assert_not_awaited()
    assert (await session.scalar(select(ResultDelivery.email_status).where(ResultDelivery.stage == "final"))) == "skipped"


async def test_the_worker_reconciles_and_sends_then_survives_errors(db, monkeypatch):
    calls = []
    monkeypatch.setattr(delivery, "reconcile", AsyncMock(side_effect=[1, RuntimeError("db down")]))
    monkeypatch.setattr(delivery, "deliver_email", AsyncMock(side_effect=[True, False]))
    monkeypatch.setattr(delivery, "EmailService", MagicMock)
    monkeypatch.setattr(delivery.get_settings().email, "smtp_host", "smtp.test")

    async def sleep(_):
        calls.append(1)
        if len(calls) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(delivery.asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await ResultDeliveryWorker(db).run()
    assert delivery.deliver_email.await_count == 2 and delivery.reconcile.await_count == 2

    worker = ResultDeliveryWorker(db)
    await worker.stop()  # never started: nothing to stop
    monkeypatch.setattr(ResultDeliveryWorker, "run", lambda self: asyncio.sleep(3600))
    worker.start()
    await worker.stop()
    assert worker.task.cancelled()
