"""The preliminary-result notification: one wording for every path, written once."""

import uuid

import pytest
from sqlalchemy import select

from app.features.notifications.models import Notification
from app.features.notifications.service import notify_once, notify_preliminary_result
from tests.unit.db_helpers import add_user, make_session_factory

HEADLINE = "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা, অফিসগামীদের চরম দুর্ভোগ"


@pytest.mark.asyncio
async def test_text_link_and_single_write():
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            user = await add_user(session)
            sid = uuid.uuid4()
            assert await notify_preliminary_result(session, user_id=user.id, submission_id=sid, headline=HEADLINE)
            # Any later VERIFICATION_COMPLETE for the same submission is the same notification.
            assert not await notify_once(
                session, user_id=user.id, notification_type="VERIFICATION_COMPLETE",
                link_url=f"/verify/{sid}", title="ignored", body="ignored", headline=HEADLINE,
            )
            rows = (await session.execute(select(Notification))).scalars().all()

        assert len(rows) == 1
        row = rows[0]
        assert row.notification_type == "VERIFICATION_COMPLETE"
        assert row.link_url == f"/verify/{sid}"
        assert row.title == "Preliminary result ready"
        assert row.body == "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা,..."
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_custom_text_is_replaced_for_verification_complete():
    """Callers' own title/body never reach the user for this type."""
    engine, factory = await make_session_factory()
    try:
        async with factory() as session:
            user = await add_user(session)
            await notify_once(
                session, user_id=user.id, notification_type="VERIFICATION_COMPLETE",
                link_url="/verify/x", title="Custom", body="Custom body", headline=None,
            )
            row = (await session.execute(select(Notification))).scalar_one()
        assert (row.title, row.body) == ("Preliminary result ready", "Your submitted claim")
    finally:
        await engine.dispose()
