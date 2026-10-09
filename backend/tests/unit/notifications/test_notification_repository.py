"""Notification queries are always scoped to their recipient."""

from datetime import datetime, timedelta, timezone

from app.features.notifications.models import Notification
from app.features.notifications.repository import NotificationRepository
from tests.helpers.db import add_user


async def test_listing_counting_and_marking_never_cross_users(session):
    me, other = await add_user(session), await add_user(session)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    notes = []
    for i, (user, read) in enumerate([(me, False), (me, True), (me, False), (other, False)]):
        n = Notification(user_id=user.id, title=f"t{i}", body="b", notification_type="X", link_url=f"/{i}", is_read=read)
        n.created_at = base + timedelta(minutes=i)
        session.add(n)
        notes.append(n)
    await session.flush()
    repo = NotificationRepository(session)

    assert [n.title for n in await repo.list_for_user(me.id, limit=10, offset=0, unread_only=False)] == ["t2", "t1", "t0"]
    assert [n.title for n in await repo.list_for_user(me.id, limit=1, offset=1, unread_only=True)] == ["t0"]
    assert await repo.count_unread(me.id) == 2

    await repo.mark_read(me.id, notes[3].id)  # someone else's: no effect
    await repo.mark_read(me.id, notes[0].id)
    assert await repo.count_unread(me.id) == 1 and await repo.count_unread(other.id) == 1
    await repo.mark_all_read(me.id)
    assert await repo.count_unread(me.id) == 0 and await repo.count_unread(other.id) == 1
