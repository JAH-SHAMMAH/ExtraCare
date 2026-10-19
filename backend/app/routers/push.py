"""Let a phone or browser opt in to alerts that arrive outside the app."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.push import PushSubscription
from app.models.user import User
from app.services import webpush

router = APIRouter(prefix="/push", tags=["Push"])


@router.get("/public-key")
async def public_key(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    _, pub = await webpush.get_vapid(db, user.org_id)
    await db.commit()
    return {"key": pub}


@router.post("/subscribe", status_code=201)
async def subscribe(body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    ep, keys = str(body.get("endpoint") or ""), body.get("keys") or {}
    p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not ep.startswith("https://") or not p256dh or not auth:
        raise HTTPException(422, "That is not a valid push subscription.")
    h = webpush.endpoint_hash(ep)
    row = (await db.execute(select(PushSubscription).where(PushSubscription.endpoint_hash == h))).scalar_one_or_none()
    if row:  # same device: re-point it at whoever is signed in now
        row.org_id, row.user_id, row.p256dh, row.auth = user.org_id, user.id, p256dh, auth
    else:
        db.add(PushSubscription(org_id=user.org_id, user_id=user.id, endpoint=ep, endpoint_hash=h, p256dh=p256dh, auth=auth,
                                user_agent=str(body.get("user_agent") or "")[:300]))
    await db.commit()
    return {"subscribed": True}


@router.post("/unsubscribe")
async def unsubscribe(body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    await db.execute(delete(PushSubscription).where(PushSubscription.endpoint_hash == webpush.endpoint_hash(str(body.get("endpoint") or "")),
                                                    PushSubscription.user_id == user.id))
    await db.commit()
    return {"subscribed": False}


@router.post("/test")
async def test_push(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    n = await webpush.send_to_user(db, user.org_id, user.id, title="Alerts are on", body="You will get school alerts on this phone.")
    return {"sent": n}
