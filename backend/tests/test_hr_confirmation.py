"""Tests for Staff Confirmation (probation → confirmed workflow). Gated hr:write.

The critical behaviour: confirming a case flips the staff member's
HRProfile.employment_status to ``active`` (creating the profile if needed);
declining leaves it untouched; a decided case can't be re-decided.
"""
from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.hrm import HRProfile
from app.core.permissions import PermissionChecker
from app.routers.hr_confirmation import (
    list_confirmations, start_confirmation, decide_confirmation, cancel_confirmation,
)
from app.schemas.hr_confirmation import ConfirmationCreate, ConfirmationDecide

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name.replace(' ', '.').lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(u)
    await db.commit()
    return u


async def _profile(db, org, user, status="probation") -> HRProfile:
    p = HRProfile(user_id=user.id, org_id=org.id, employment_status=status)
    db.add(p)
    await db.commit()
    return p


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


async def test_confirm_flips_employment_status(db, org, teacher):
    staff = await _staff(db, org, "Prob Ationer")
    await _profile(db, org, staff, status="probation")
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id, probation_start=date(2026, 1, 1), due_date=date(2026, 7, 1)),
                                 db=db, current_user=teacher)
    assert c.status == "pending" and c.employment_status == "probation"

    decided = await decide_confirmation(c.id, ConfirmationDecide(decision="confirm", notes="Great year"), db=db, current_user=teacher)
    assert decided.status == "confirmed" and decided.employment_status == "active"

    prof = (await db.execute(select(HRProfile).where(HRProfile.user_id == staff.id))).scalar_one()
    assert prof.employment_status == "active"      # the real staff record changed


async def test_confirm_creates_profile_if_missing(db, org, teacher):
    staff = await _staff(db, org, "No Profile")      # no HRProfile yet
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id), db=db, current_user=teacher)
    decided = await decide_confirmation(c.id, ConfirmationDecide(decision="confirm"), db=db, current_user=teacher)
    assert decided.employment_status == "active"
    prof = (await db.execute(select(HRProfile).where(HRProfile.user_id == staff.id))).scalar_one_or_none()
    assert prof is not None and prof.employment_status == "active"


async def test_decline_leaves_status_untouched(db, org, teacher):
    staff = await _staff(db, org, "Declined One")
    await _profile(db, org, staff, status="probation")
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id), db=db, current_user=teacher)
    decided = await decide_confirmation(c.id, ConfirmationDecide(decision="decline", notes="Extend probation"), db=db, current_user=teacher)
    assert decided.status == "declined" and decided.employment_status == "probation"


async def test_cannot_redecide(db, org, teacher):
    staff = await _staff(db, org, "Once Only")
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id), db=db, current_user=teacher)
    await decide_confirmation(c.id, ConfirmationDecide(decision="confirm"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await decide_confirmation(c.id, ConfirmationDecide(decision="decline"), db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_cancel_pending_only(db, org, teacher):
    staff = await _staff(db, org, "Cancel Me")
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id), db=db, current_user=teacher)
    await cancel_confirmation(c.id, db=db, current_user=teacher)
    assert c.id not in [x.id for x in await list_confirmations(status=None, db=db, current_user=teacher)]

    staff2 = await _staff(db, org, "Decided One")
    c2 = await start_confirmation(ConfirmationCreate(staff_user_id=staff2.id), db=db, current_user=teacher)
    await decide_confirmation(c2.id, ConfirmationDecide(decision="confirm"), db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await cancel_confirmation(c2.id, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_start_unknown_staff_404_and_org_isolation(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await start_confirmation(ConfirmationCreate(staff_user_id="nope"), db=db, current_user=teacher)
    assert exc.value.status_code == 404
    staff = await _staff(db, org, "Mine Conf")
    c = await start_confirmation(ConfirmationCreate(staff_user_id=staff.id), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    assert c.id not in [x.id for x in await list_confirmations(status=None, db=db, current_user=other)]


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_confirmation_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
