import gzip
import json
import uuid

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers import admin as admin_router

pytestmark = pytest.mark.asyncio


class _Req:
    headers: dict = {}
    client = type("C", (), {"host": "127.0.0.1"})()
    url = type("U", (), {"path": "/x"})()


def _user(org, perms, pw="Correct-Horse-9"):
    u = User(id=str(uuid.uuid4()), email=f"d-{uuid.uuid4().hex[:6]}@x.com", full_name="Director",
             status=UserStatus.ACTIVE, org_id=org.id, hashed_password=hash_password(pw))
    u.roles = [Role(id=str(uuid.uuid4()), name="r", slug=f"r{uuid.uuid4().hex[:4]}",
                    permissions=perms, org_id=org.id, is_system=False)]
    return u


async def _call(db, engine, user, pw, monkeypatch):
    monkeypatch.setattr(admin_router, "engine", engine)
    return await admin_router.download_backup(
        admin_router.BackupRequest(password=pw), _Req(), db=db, current_user=user)


async def test_director_gets_a_readable_full_backup(db, engine, org, monkeypatch):
    u = _user(org, ["*"])
    db.add(u)
    await db.commit()
    resp = await _call(db, engine, u, "Correct-Horse-9", monkeypatch)
    lines = [json.loads(l) for l in gzip.open(resp.path, "rt")]
    assert lines[0]["_meta"]["format"] == "fairview-logical-v1"
    assert lines[-1]["_end"] is True
    assert lines[-1]["counts"]["users"] >= 1
    assert resp.headers["cache-control"] == "no-store"


async def test_wrong_password_refused(db, engine, org, monkeypatch):
    u = _user(org, ["*"])
    db.add(u)
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await _call(db, engine, u, "nope", monkeypatch)
    assert e.value.status_code == 403


async def test_ordinary_admin_refused(db, engine, org, monkeypatch):
    u = _user(org, ["school:*", "school_admin:*"])
    db.add(u)
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await _call(db, engine, u, "Correct-Horse-9", monkeypatch)
    assert e.value.status_code == 403
