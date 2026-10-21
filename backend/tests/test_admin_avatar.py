"""Admin-set avatar: POST /upload/avatar/{user_id} (users:write) sets another
user's photo, org-scoped. Powers photo-rich directories + the feed Select-Users
modal. The storage write (save_upload) is monkeypatched so tests don't touch
./uploads or Cloudinary."""
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
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 120, 60)).save(buf, "PNG")
    return UploadFile(
        file=io.BytesIO(buf.getvalue()),
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


async def _fake_save(org_id, kind, filename, content, content_type=""):
    return f"/uploads/{org_id}/{kind}/f.png"


async def test_admin_sets_another_users_avatar(db, org, monkeypatch):
    monkeypatch.setattr(up, "save_upload", _fake_save)
    admin = await _user(db, org, "Admin")
    target = await _user(db, org, "Target")

    res = await up.upload_avatar_for_user(user_id=target.id, file=_png(), db=db, current_user=admin)
    assert res["user_id"] == target.id and res["url"].endswith("/avatars/f.png")

    await db.refresh(target)
    assert target.avatar_url == res["url"]


async def test_admin_avatar_rejects_unknown_or_cross_org(db, org, monkeypatch):
    monkeypatch.setattr(up, "save_upload", _fake_save)
    admin = await _user(db, org, "Admin")
    # Unknown id → 404 (checked before the file is even read).
    with pytest.raises(HTTPException) as exc:
        await up.upload_avatar_for_user(user_id="does-not-exist", file=_png(), db=db, current_user=admin)
    assert exc.value.status_code == 404


async def test_own_avatar_also_sets_linked_student_photo(db, org, monkeypatch):
    from app.models.modules.school import Student
    monkeypatch.setattr(up, "save_upload", _fake_save)
    u = await _user(db, org, "Pupil")
    st = Student(id=str(uuid.uuid4()), student_id="S1", first_name="P", last_name="Q", org_id=org.id, user_id=u.id)
    db.add(st)
    await db.commit()
    res = await up.upload_avatar(file=_png(), db=db, current_user=u)
    await db.refresh(st)
    assert st.photo_url == res["url"]
