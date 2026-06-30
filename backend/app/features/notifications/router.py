"""
app/features/notifications/router.py
=====================================
Notification API endpoints.

GET  /api/v1/notifications         — Paginated notification list for current user
GET  /api/v1/notifications/count   — Unread notification count
POST /api/v1/notifications/{id}/read     — Mark single notification as read
POST /api/v1/notifications/read-all     — Mark all notifications as read
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import User
from app.features.auth.security import get_current_user
from app.features.notifications.models import Notification
from app.shared.dependencies import get_async_session

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: str
    title: str
    body: str
    notification_type: str
    link_url: str | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int


@router.get("", response_model=list[NotificationResponse], summary="List notifications")
async def list_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[NotificationResponse]:
    """Return the current user's notifications, most recent first."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    notifications = result.scalars().all()
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
    session: AsyncSession = Depends(get_async_session),
) -> UnreadCountResponse:
    """Return the number of unread notifications for the current user."""
    stmt = (
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
    )
    count = (await session.execute(stmt)).scalar_one()
    return UnreadCountResponse(unread_count=count)


@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark single notification as read",
)
async def mark_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Mark one notification as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .values(is_read=True)
    )
    await session.execute(stmt)
    await session.flush()


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """Mark all unread notifications for the current user as read."""
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await session.execute(stmt)
    await session.flush()
