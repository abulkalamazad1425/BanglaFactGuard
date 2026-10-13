from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.notifications.models import Notification
from app.shared.utils.headline_preview import headline_preview

logger = structlog.get_logger(__name__)


def preliminary_notification_text(headline: str | None) -> tuple[str, str]:
    return "Preliminary result ready", headline_preview(headline) or "Your submitted claim"


def final_notification_text(headline: str | None, verdict_label: str | None) -> tuple[str, str]:
    title = f"Final decision: {verdict_label}" if verdict_label else "Final decision ready"
    return title, headline_preview(headline) or "Your submitted claim"


async def notify_preliminary_result(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    submission_id: uuid.UUID,
    headline: str | None,
) -> bool:
    title, body = preliminary_notification_text(headline)
    return await notify_once(
        session,
        user_id=user_id,
        notification_type="VERIFICATION_COMPLETE",
        link_url=f"/verify/{submission_id}",
        title=title,
        body=body,
        headline=headline,
    )


async def notify_once(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    link_url: str,
    title: str,
    body: str,
    headline: str | None = None,
) -> bool:
    if notification_type == "VERIFICATION_COMPLETE":
        title, body = preliminary_notification_text(headline)
    try:
        existing = (
            await session.execute(
                select(Notification.id)
                .where(
                    Notification.user_id == user_id,
                    Notification.notification_type == notification_type,
                    Notification.link_url == link_url,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return False
        async with session.begin_nested():
            session.add(
                Notification(
                    user_id=user_id,
                    title=title[:255],
                    body=body,
                    notification_type=notification_type,
                    link_url=link_url[:512],
                    is_read=False,
                )
            )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("notification_write_failed", type=notification_type, error=str(exc))
        return False
