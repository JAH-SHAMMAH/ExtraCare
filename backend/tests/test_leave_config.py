"""Tests for Leave completion — Configure (policies), Entitlements, Assign.

Keeps the existing LeaveType enum; layers policy + computed balances + admin
on-behalf assignment. Covers defaults, upsert, used-vs-remaining, inactive-type
exclusion, the hr:write gate on viewing others' entitlements, and assign rules.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.leave import LeaveType
from app.routers.leave_config import list_policies, upsert_policy, entitlements, assign_leave
from app.schemas.leave_config import LeavePolicyUpdate, AssignLeaveCreate

pytestmark = pytest.mark.asyncio

YEAR = date.today().year


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Configure ─────────────────────────────────────────────────────────────────

async def test_policies_seed_defaults(db, org, teacher):
    rows = await list_policies(db=db, current_user=teacher)
    by = {r.leave_type: r for r in rows}
    assert len(rows) == len(list(LeaveType))
    assert by["annual"].default_days == 20 and by["annual"].is_active is True
    assert by["sick"].default_days == 10


async def test_upsert_policy(db, org, teacher):
    updated = await upsert_policy(LeaveType.ANNUAL, LeavePolicyUpdate(default_days=25, requires_approval=False, is_active=True), db=db, current_user=teacher)
    assert updated.default_days == 25 and updated.requires_approval is False
    rows = {r.leave_type: r for r in await list_policies(db=db, current_user=teacher)}
    assert rows["annual"].default_days == 25          # persisted


# ── Entitlements ──────────────────────────────────────────────────────────────

async def test_entitlements_used_and_remaining(db, org):
    admin = await _preset_user(db, org, "org_admin")
    staff = await _staff(db, org, "Balance Guy")
    # Admin assigns 4 days annual to staff (approved) → used = 4.
    await assign_leave(AssignLeaveCreate(user_id=staff.id, leave_type=LeaveType.ANNUAL,
                                         start_date=date(YEAR, 3, 1), end_date=date(YEAR, 3, 4)), db=db, current_user=admin)
    rows = {r.leave_type: r for r in await entitlements(user_id=staff.id, db=db, current_user=admin)}
    assert rows["annual"].used == 4
    assert rows["annual"].remaining == rows["annual"].allocated - 4


async def test_entitlements_excludes_inactive_type(db, org, teacher):
    await upsert_policy(LeaveType.OTHER, LeavePolicyUpdate(default_days=0, requires_approval=True, is_active=False), db=db, current_user=teacher)
    rows = await entitlements(user_id=None, db=db, current_user=teacher)
    assert "other" not in {r.leave_type for r in rows}


async def test_entitlements_self_is_default(db, org):
    staff = await _staff(db, org, "Self View")
    rows = await entitlements(user_id=None, db=db, current_user=staff)
    assert all(r.used == 0 for r in rows)             # no leave taken yet
    assert {r.leave_type for r in rows}               # returns the active types


async def test_entitlements_others_requires_hr_write(db, org):
    teacher = await _preset_user(db, org, "teacher")
    other = await _staff(db, org, "Someone")
    assert not teacher.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await entitlements(user_id=other.id, db=db, current_user=teacher)
    assert exc.value.status_code == 403


# ── Assign ────────────────────────────────────────────────────────────────────

async def test_assign_creates_approved(db, org):
    admin = await _preset_user(db, org, "org_admin")
    staff = await _staff(db, org, "Assignee")
    app = await assign_leave(AssignLeaveCreate(user_id=staff.id, leave_type=LeaveType.CASUAL,
                                               start_date=date(YEAR, 5, 1), end_date=date(YEAR, 5, 2)), db=db, current_user=admin)
    assert app.status.value == "approved" and app.days == 2 and app.user_id == staff.id
    assert app.approver_id == admin.id


async def test_assign_bad_dates_and_unknown_user(db, org):
    admin = await _preset_user(db, org, "org_admin")
    staff = await _staff(db, org, "X")
    with pytest.raises(HTTPException) as e1:
        await assign_leave(AssignLeaveCreate(user_id=staff.id, leave_type=LeaveType.ANNUAL,
                                             start_date=date(YEAR, 5, 5), end_date=date(YEAR, 5, 1)), db=db, current_user=admin)
    assert e1.value.status_code == 422
    with pytest.raises(HTTPException) as e2:
        await assign_leave(AssignLeaveCreate(user_id="nope", leave_type=LeaveType.ANNUAL,
                                             start_date=date(YEAR, 5, 1), end_date=date(YEAR, 5, 2)), db=db, current_user=admin)
    assert e2.value.status_code == 404
