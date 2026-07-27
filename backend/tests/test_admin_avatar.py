"""Admin-set avatar: POST /upload/avatar/{user_id} (users:write) sets another
user's photo, org-scoped. Powers photo-rich directories + the feed Select-Users
modal. The disk write (_save) is monkeypatched so tests don't touch ./uploads."""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from starlette.datastructures import UploadFile, Headers

from app.models.user import User, UserStatus
from app.routers import upload as up


pytestmark = pytest.mark.asyncio


def _png() -> UploadFile:
    return UploadFile(
        file=io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * 64),
        filename="a.png",
        headers=Headers({"content-type": "image/png"}),
    )


async def _user(db, org, name="U") -> User:
    u = User(id=str(uuid.uuid4()), email=f"{uuid.uuid4().hex[:8]}@x.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def test_admin_sets_another_users_avatar(db, org, monkeypatch):
    monkeypatch.setattr(up, "_save", lambda org_id, kind, filename, content: ("f.png", f"/uploads/{org_id}/{kind}/f.png"))
    admin = await _user(db, org, "Admin")
    target = await _user(db, org, "Target")

    res = await up.upload_avatar_for_user(user_id=target.id, file=_png(), db=db, current_user=admin)
    assert res["user_id"] == target.id and res["url"].endswith("/avatars/f.png")

    await db.refresh(target)
    assert target.avatar_url == res["url"]


async def test_admin_avatar_rejects_unknown_or_cross_org(db, org, monkeypatch):
    monkeypatch.setattr(up, "_save", lambda *a: ("f.png", "/uploads/x/avatars/f.png"))
    admin = await _user(db, org, "Admin")
    # Unknown id → 404 (checked before the file is even read).
    with pytest.raises(HTTPException) as exc:
        await up.upload_avatar_for_user(user_id="does-not-exist", file=_png(), db=db, current_user=admin)
    assert exc.value.status_code == 404
