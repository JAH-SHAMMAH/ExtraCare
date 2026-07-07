"""Tests for admin password reset + self-service change-password.

Proves the security flow the User Roles consolidation added:
  • admin reset sets a temp password + force_password_change, returns the temp
    (so it can be handed over), and is audited
  • an admin can't reset their own account this way; unknown user 404s
  • change-password verifies the current password, enforces strength, rejects a
    no-op, and CLEARS the force flag on success
  • /me exposes force_password_change so the client can enforce the change
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.user import User, UserStatus
from app.core.security import verify_password, hash_password
from app.routers.users import reset_user_password
from app.routers.auth import change_password
from app.schemas.auth import ChangePasswordRequest, UserMeResponse

pytestmark = pytest.mark.asyncio


async def _user(db, org, pw="OldPass123") -> User:
    u = User(id=str(uuid.uuid4()), email=f"u-{uuid.uuid4().hex[:6]}@ex.com", full_name="Target",
             status=UserStatus.ACTIVE, org_id=org.id, hashed_password=hash_password(pw))
    u.roles = []  # assign while transient so the collection reads as loaded (no async lazyload)
    db.add(u)
    await db.commit()
    return u


# ── Admin reset ──────────────────────────────────────────────────────────────────

async def test_admin_reset_sets_temp_and_flag(db, org, teacher):
    target = await _user(db, org)
    res = await reset_user_password(target.id, request=None, db=db, current_user=teacher)
    assert res["temporary_password"] and res["force_password_change"] is True
    await db.refresh(target)
    assert target.force_password_change is True
    assert verify_password(res["temporary_password"], target.hashed_password)


async def test_cannot_reset_self(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await reset_user_password(teacher.id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 400


async def test_reset_unknown_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await reset_user_password(str(uuid.uuid4()), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Self-service change ───────────────────────────────────────────────────────────

async def test_change_password_clears_flag(db, org):
    u = await _user(db, org, pw="OldPass123")
    u.force_password_change = True
    await db.commit()
    res = await change_password(
        ChangePasswordRequest(current_password="OldPass123", new_password="NewPass456"),
        request=None, current_user=u, db=db,
    )
    assert res["changed"] is True
    await db.refresh(u)
    assert u.force_password_change is False
    assert verify_password("NewPass456", u.hashed_password)


async def test_change_password_wrong_current(db, org):
    u = await _user(db, org, pw="OldPass123")
    with pytest.raises(HTTPException) as exc:
        await change_password(
            ChangePasswordRequest(current_password="WRONG", new_password="NewPass456"),
            request=None, current_user=u, db=db,
        )
    assert exc.value.status_code == 400


async def test_change_password_weak_rejected(db, org):
    u = await _user(db, org, pw="OldPass123")
    # 12 chars but no uppercase / digit -> strength violation (422), not a schema error
    with pytest.raises(HTTPException) as exc:
        await change_password(
            ChangePasswordRequest(current_password="OldPass123", new_password="alllowercase"),
            request=None, current_user=u, db=db,
        )
    assert exc.value.status_code == 422


async def test_change_password_must_differ(db, org):
    u = await _user(db, org, pw="OldPass123")
    with pytest.raises(HTTPException) as exc:
        await change_password(
            ChangePasswordRequest(current_password="OldPass123", new_password="OldPass123"),
            request=None, current_user=u, db=db,
        )
    assert exc.value.status_code == 422


async def test_schema_min_length():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="x", new_password="short")


async def test_me_exposes_flag(db, org):
    u = await _user(db, org)
    u.force_password_change = True
    resp = UserMeResponse.from_user(u, None)
    assert resp.force_password_change is True
