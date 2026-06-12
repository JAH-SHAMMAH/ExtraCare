"""
Notifications API — inbox read + mark-read.

Polling-friendly: the list endpoint is cheap, and clients hit it every
30–60s. No WebSocket yet — cost/benefit for the current user count
doesn't justify it. When it does, swap this router's backend without
changing the wire shape.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.services import notifications as notif_svc


router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _serialize(n) -> dict:
    return {
        "id": n.id,
        "org_id": n.org_id,
        "user_id": n.user_id,
        "type": n.type,
        "title": n.title,
        "message": n.message,
        "payload": n.payload or {},
        "read": bool(n.read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("", summary="List notifications for the current user")
async def list_notifications(
    unread_only: bool = Query(False),
    type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    rows = await notif_svc.list_for(
        db,
        org_id=current_user.org_id,
        user_id=current_user.id,
        unread_only=unread_only,
        notif_type=type,
        limit=limit,
    )
    unread = await notif_svc.unread_count(
        db, org_id=current_user.org_id, user_id=current_user.id,
    )
    return {
        "unread_count": unread,
        "items": [_serialize(r) for r in rows],
    }


@router.patch("/{notification_id}/read", summary="Mark a single notification as read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ok = await notif_svc.mark_read(
        db,
        org_id=current_user.org_id,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    if not ok:
        # Either not found, in another tenant, or addressed to a different
        # user — surface a generic 404 to avoid leaking existence.
        raise HTTPException(status_code=404, detail="Notification not found.")
    await db.commit()
    return {"id": notification_id, "read": True}


@router.patch("/read-all", summary="Mark every unread notification visible to the user")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    n = await notif_svc.mark_all_read(
        db, org_id=current_user.org_id, user_id=current_user.id,
    )
    await db.commit()
    return {"marked": n}
