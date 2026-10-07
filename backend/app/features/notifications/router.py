from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.notifications.repository import NotificationRepository
from app.features.notifications.schemas import NotificationResponse, UnreadCountResponse
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _repo(session: AsyncSession = Depends(get_async_session)) -> NotificationRepository:
    return NotificationRepository(session)


@router.get("", response_model=list[NotificationResponse], summary="List notifications")
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(_repo),
) -> list[NotificationResponse]:
    notifications = await repo.list_for_user(
        current_user.id, limit=limit, offset=offset, unread_only=unread_only
    )
    return [
        NotificationResponse(
            id=str(n.id),
            title=n.title,
            body=n.body,
            notification_type=n.notification_type,
            link_url=n.link_url,
            is_read=n.is_read,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.get("/count", response_model=UnreadCountResponse, summary="Unread count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(_repo),
) -> UnreadCountResponse:
    return UnreadCountResponse(unread_count=await repo.count_unread(current_user.id))


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark single notification as read",
)
async def mark_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(_repo),
) -> None:
    await repo.mark_read(current_user.id, notification_id)


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    repo: NotificationRepository = Depends(_repo),
) -> None:
    await repo.mark_all_read(current_user.id)
