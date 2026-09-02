"""Admin-initiated password reset is privilege-guarded.

`POST /users/{id}/reset-password` hands the caller a WORKING credential for
another account (the temp password comes back in the response body), so it is a
full takeover of that account in one call. It was gated on `users:write` alone —
which ten roles hold, including hr_manager — so any of them could seize the Super
User's account. It now carries `assert_can_manage_user`, the same guard already
on role assignment.

The rule that guard implements: you may manage a user only when you already hold
every permission their roles carry. Note what that does and does not mean —
  • strictly MORE privileged target  -> blocked (the hole being closed)
  • identical privilege              -> allowed (peer admins can recover each other)
  • merely DIFFERENTLY scoped target -> also blocked, because "holds a permission
    you lack" cannot distinguish "above you" from "sideways of you"
The third case is load-bearing for anyone designing a narrow helpdesk role: it is
why such a role cannot reset an ordinary teacher's password.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.users import reset_user_password

pytestmark = pytest.mark.asyncio


async def _user(db, org, slug: str, permissions: list[str] | None = None) -> User:
    """A user carrying one role — the preset for `slug` unless overridden."""
    perms = permissions if permissions is not None else list(SCHOOL_PERMISSION_PRESETS[slug])
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=perms, org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.replace("_", " ").title(), status=UserStatus.ACTIVE,
             hashed_password="x", org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def test_lower_tier_admin_cannot_reset_super_user(db, org):
    """The takeover this closes: hr_manager holds users:write, super_user holds
    '*' — so hr_manager could mint themselves a working Super User credential."""
    hr = await _user(db, org, "hr_manager")
    boss = await _user(db, org, "super_user")

    with pytest.raises(HTTPException) as exc:
        await reset_user_password(boss.id, request=None, db=db, current_user=hr)
    assert exc.value.status_code == 403
    assert "higher privileges" in exc.value.detail

    await db.refresh(boss)
    assert boss.hashed_password == "x"          # untouched
    assert boss.force_password_change is not True


async def test_lower_tier_admin_cannot_reset_org_admin(db, org):
    hr = await _user(db, org, "hr_manager")
    admin = await _user(db, org, "org_admin")

    with pytest.raises(HTTPException) as exc:
        await reset_user_password(admin.id, request=None, db=db, current_user=hr)
    assert exc.value.status_code == 403


async def test_super_user_can_reset_anyone(db, org):
    """'*' covers every permission, so the top tier is never blocked — the
    break-glass path stays open."""
    boss = await _user(db, org, "super_user")
    admin = await _user(db, org, "org_admin")

    out = await reset_user_password(admin.id, request=None, db=db, current_user=boss)
    assert out["force_password_change"] is True
    assert out["temporary_password"]

    await db.refresh(admin)
    assert admin.hashed_password != "x"
    assert admin.force_password_change is True


async def test_peer_of_equal_privilege_is_allowed(db, org):
    """Identical scope sets leave nothing uncovered, so peer admins can still
    recover each other's accounts. Deliberate: the guard blocks climbing, not
    same-tier support."""
    one = await _user(db, org, "org_admin")
    two = await _user(db, org, "org_admin")

    out = await reset_user_password(two.id, request=None, db=db, current_user=one)
    assert out["temporary_password"]


async def test_admin_can_reset_a_strictly_narrower_account(db, org):
    """org_admin's scopes cover a teacher's, so ordinary support still works."""
    admin = await _user(db, org, "org_admin")
    teacher = await _user(db, org, "teacher")

    out = await reset_user_password(teacher.id, request=None, db=db, current_user=admin)
    assert out["temporary_password"]
    await db.refresh(teacher)
    assert teacher.force_password_change is True


async def test_sideways_scope_is_also_blocked(db, org):
    """The consequence to design around: a narrow account-management role is
    blocked from an ordinary teacher too, because the teacher holds school
    scopes it lacks. Not "more privileged" — just different. Pinned here so the
    behaviour is a decision, not a surprise."""
    ict = await _user(db, org, "it_support",
                      permissions=["users:read", "users:write", "roles:read", "roles:write"])
    teacher = await _user(db, org, "teacher")

    with pytest.raises(HTTPException) as exc:
        await reset_user_password(teacher.id, request=None, db=db, current_user=ict)
    assert exc.value.status_code == 403


async def test_self_reset_still_redirected(db, org):
    """Unchanged: your own password goes through change-password, and the
    self-check runs before the guard (which exempts self anyway)."""
    admin = await _user(db, org, "org_admin")
    with pytest.raises(HTTPException) as exc:
        await reset_user_password(admin.id, request=None, db=db, current_user=admin)
    assert exc.value.status_code == 400


async def test_missing_user_still_404s(db, org):
    admin = await _user(db, org, "org_admin")
    with pytest.raises(HTTPException) as exc:
        await reset_user_password(str(uuid.uuid4()), request=None, db=db, current_user=admin)
    assert exc.value.status_code == 404


async def test_cross_org_target_is_not_reachable(db, org):
    """Tenant isolation is unchanged by the guard — a different org's user is a
    404, not a 403 (we don't confirm the account exists)."""
    from app.models.organization import Organization, IndustryType

    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()

    admin = await _user(db, org, "org_admin")
    stranger = await _user(db, other, "teacher")

    with pytest.raises(HTTPException) as exc:
        await reset_user_password(stranger.id, request=None, db=db, current_user=admin)
    assert exc.value.status_code == 404
