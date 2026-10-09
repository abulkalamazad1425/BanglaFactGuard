"""In-app notifications are written once per (user, type, link), with one
wording for every preliminary result; a write failure never raises."""

import uuid
from unittest.mock import MagicMock

from sqlalchemy import select

from app.features.notifications.models import Notification
from app.features.notifications.service import (
    final_notification_text,
    notify_once,
    notify_preliminary_result,
)
from tests.helpers.db import add_user

HEADLINE = "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা, অফিসগামীদের চরম দুর্ভোগ"


async def test_the_preliminary_notice_has_one_wording_and_is_written_once(session):
    user = await add_user(session)
    sid = uuid.uuid4()
    assert await notify_preliminary_result(session, user_id=user.id, submission_id=sid, headline=HEADLINE)
    # any later VERIFICATION_COMPLETE for the same submission is the same notice
    assert not await notify_once(session, user_id=user.id, notification_type="VERIFICATION_COMPLETE",
                                 link_url=f"/verify/{sid}", title="ignored", body="ignored", headline=HEADLINE)
    # callers' own text never reaches the user for this type
    await notify_once(session, user_id=user.id, notification_type="VERIFICATION_COMPLETE", link_url="/verify/x",
                      title="Custom", body="Custom body", headline=None)
    rows = (await session.execute(select(Notification).order_by(Notification.link_url))).scalars().all()
    assert [(r.link_url, r.title, r.body) for r in rows] == [
        (f"/verify/{sid}", "Preliminary result ready", "ঢাকায় আজ ভারী বৃষ্টিতে জলাবদ্ধতা,..."),
        ("/verify/x", "Preliminary result ready", "Your submitted claim"),
    ]


async def test_other_types_keep_their_text_and_failures_are_swallowed(session):
    user = await add_user(session)
    assert await notify_once(session, user_id=user.id, notification_type="VERIFICATION_FAILED", link_url="/verify/y",
                             title="Verification could not be completed", body="Card unreadable.")
    row = (await session.execute(select(Notification))).scalar_one()
    assert (row.title, row.body, row.is_read) == ("Verification could not be completed", "Card unreadable.", False)
    broken = MagicMock(execute=MagicMock(side_effect=RuntimeError("db down")))
    assert await notify_once(broken, user_id=user.id, notification_type="X", link_url="/", title="t", body="b") is False


def test_final_notice_text():
    assert final_notification_text("এক দুই তিন চার পাঁচ ছয়", "Fake") == ("Final decision: Fake", "এক দুই তিন চার পাঁচ...")
    assert final_notification_text(None, None) == ("Final decision ready", "Your submitted claim")
