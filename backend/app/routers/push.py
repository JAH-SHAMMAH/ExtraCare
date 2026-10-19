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

# Only the real browser push services. The server posts to the address it is given,
# so anything else could be used to make us call internal or arbitrary hosts.
_PUSH_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "notify.windows.com", "push.apple.com", "web.push.apple.com")


def _is_push_service(endpoint: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(endpoint).hostname or "").lower()
    return endpoint.startswith("https://") and any(host == h or host.endswith("." + h) for h in _PUSH_HOSTS)


@router.get("/public-key")
async def public_key(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    _, pub = await webpush.get_vapid(db, user.org_id)
    await db.commit()
    return {"key": pub}


@router.post("/subscribe", status_code=201)
async def subscribe(body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    ep, keys = str(body.get("endpoint") or ""), body.get("keys") or {}
    p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    if not _is_push_service(ep) or not p256dh or not auth:
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


# The kinds of alert a person can choose between. Anything not listed counts as "other".
ALERT_KINDS = {
    "attendance": "My child arrives at or leaves school",
    "report": "My child's report is published",
    "other": "Everything else (messages, notices, fees)",
}


def alert_choices(user: User) -> dict:
    saved = (user.preferences or {}).get("push_alerts") or {}
    return {k: bool(saved.get(k, True)) for k in ALERT_KINDS}


@router.get("/prefs")
async def get_prefs(user: User = Depends(get_current_active_user)):
    return {"kinds": ALERT_KINDS, "values": alert_choices(user)}


@router.put("/prefs")
async def put_prefs(body: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_active_user)):
    from sqlalchemy.orm.attributes import flag_modified
    vals = body.get("values")
    if not isinstance(vals, dict) or not all(k in ALERT_KINDS and isinstance(v, bool) for k, v in vals.items()):
        raise HTTPException(422, "Send {\"values\": {kind: true/false}}.")
    prefs = dict(user.preferences or {})
    prefs["push_alerts"] = {**alert_choices(user), **vals}
    user.preferences = prefs
    flag_modified(user, "preferences")
    await db.commit()
    return {"kinds": ALERT_KINDS, "values": alert_choices(user)}
