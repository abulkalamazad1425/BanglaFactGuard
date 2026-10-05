from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import ARRAY, select, func
from sqlalchemy.ext.compiler import compiles

from app.core.constants import OverallVerdict, SubmissionStatus, SubmissionType, MultimodalPredictionLabel
from app.features.multimodal.models import MultimodalAnalysis
from app.features.notifications.delivery import reconcile, deliver_email
from app.features.notifications.models import Notification, ResultDelivery
from app.shared.models_registry import Base
from tests.unit.db_helpers import make_session_factory, add_user, add_completed_submission


@compiles(ARRAY, 'sqlite')
def array_sqlite(*args, **kwargs):
    return 'JSON'


@pytest.fixture
async def database():
    engine, factory = await make_session_factory()
    async with engine.begin() as connection:
        await connection.run_sync(lambda c: Base.metadata.create_all(c, tables=[MultimodalAnalysis.__table__, ResultDelivery.__table__]))
    yield factory
    await engine.dispose()


@pytest.mark.parametrize('role', ['user', 'expert', 'admin'])
@pytest.mark.parametrize('kind', list(SubmissionType))
async def test_personal_preliminary_and_final_are_deduplicated_for_each_role_and_method(database, role, kind):
    async with database() as session:
        user = await add_user(session, role=role)
        sub, result = await add_completed_submission(session, headline='A claim', submitter_id=user.id, submission_type=kind)
        if kind == SubmissionType.MULTIMODAL:
            await session.delete(result)
            result = MultimodalAnalysis(submission_id=sub.id, image_object_key='image', prediction=MultimodalPredictionLabel.FAKE,
                                        confidence_fake=.8, confidence_real=.2, model_version='test')
            session.add(result)
        await session.commit()
        assert await reconcile(session) == 1
        assert await reconcile(session) == 0
        assert await session.scalar(select(func.count()).select_from(Notification)) == 1
        sub.status = SubmissionStatus.FINALIZED
        if kind == SubmissionType.MULTIMODAL:
            result.expert_overall_verdict = OverallVerdict.REAL
        else:
            result.overall_verdict = OverallVerdict.REAL
        await session.flush()
        assert await reconcile(session) == 1
        assert await reconcile(session) == 0
        notices = (await session.scalars(select(Notification))).all()
        assert len(notices) == 2
        assert all(n.user_id == user.id and n.link_url == f'/verify/{sub.id}' for n in notices)
        mail = AsyncMock()
        assert await deliver_email(session, mail)
        mail.send_result_email.assert_awaited_once()
        assert mail.send_result_email.call_args.kwargs['to_email'] == user.email
        assert mail.send_result_email.call_args.kwargs['verdict'] == 'Real'
        assert not await deliver_email(session, mail)


async def test_guests_do_not_receive_account_notifications_or_email(database):
    async with database() as session:
        await add_completed_submission(session, headline='Guest', submitter_id=None, overall_verdict=OverallVerdict.FAKE)
        assert await reconcile(session) == 0
        assert await session.scalar(select(func.count()).select_from(Notification)) == 0


async def test_reused_source_claim_follows_original_final_verdict(database):
    async with database() as session:
        user = await add_user(session)
        original, result = await add_completed_submission(session, headline='Original', submitter_id=None)
        copy, copied = await add_completed_submission(session, headline='Original', submitter_id=user.id)
        copy.duplicate_of_submission_id = original.id
        copied.reused_from_submission_id = original.id
        await session.flush()
        assert await reconcile(session) == 1
        original.status = SubmissionStatus.FINALIZED
        result.overall_verdict = OverallVerdict.ALTERED
        await session.flush()
        assert await reconcile(session) == 1
        mail = AsyncMock()
        await deliver_email(session, mail)
        assert mail.send_result_email.call_args.kwargs['submission_id'] == str(copy.id)
        assert mail.send_result_email.call_args.kwargs['verdict'] == 'Altered'


async def test_smtp_failure_retries_without_duplicating_notifications(database):
    async with database() as session:
        user = await add_user(session)
        sub, _ = await add_completed_submission(session, headline='Final', submitter_id=user.id, overall_verdict=OverallVerdict.FAKE)
        await reconcile(session)
        mail = AsyncMock()
        mail.send_result_email.side_effect = RuntimeError('SMTP offline')
        assert await deliver_email(session, mail)
        row = await session.get(ResultDelivery, (sub.id, 'final'))
        assert row.email_status == 'pending' and row.email_attempts == 1
        assert not await deliver_email(session, mail)
        row.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.flush()
        mail.send_result_email.side_effect = None
        assert await deliver_email(session, mail)
        assert row.email_status == 'sent'
        assert await reconcile(session) == 0
        assert await session.scalar(select(func.count()).select_from(Notification)) == 2
