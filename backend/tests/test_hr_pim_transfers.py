"""Tests for PIM › Staff Transfer Log.

A transfer both LOGS the move (snapshotting the prior department) and updates the
staff member's live ``User.department``. Gated hr:write.
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
from app.core.permissions import PermissionChecker
from app.routers.hr_pim import create_transfer, list_transfers
from app.schemas.hr_pim import TransferCreate

pytestmark = pytest.mark.asyncio


async def _staff(db, org, name, department=None) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name.replace(' ', '.').lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id, department=department)
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


async def test_transfer_logs_and_updates_department(db, org, teacher):
    staff = await _staff(db, org, "Mover One", department="Academics")
    t = await create_transfer(
        TransferCreate(staff_user_id=staff.id, to_department="Administration", to_unit="Front Office",
                       effective_date=date(2026, 8, 1), reason="Reassignment"),
        db=db, current_user=teacher,
    )
    assert t.from_department == "Academics" and t.to_department == "Administration" and t.to_unit == "Front Office"

    # The live staff record moved.
    moved = (await db.execute(select(User).where(User.id == staff.id))).scalar_one()
    assert moved.department == "Administration"

    # And it shows in history.
    hist = await list_transfers(staff_user_id=staff.id, db=db, current_user=teacher)
    assert len(hist) == 1 and hist[0].to_department == "Administration" and hist[0].staff_name == "Mover One"


async def test_second_transfer_snapshots_prior_department(db, org, teacher):
    staff = await _staff(db, org, "Chain Two", department="A")
    await create_transfer(TransferCreate(staff_user_id=staff.id, to_department="B"), db=db, current_user=teacher)
    t2 = await create_transfer(TransferCreate(staff_user_id=staff.id, to_department="C"), db=db, current_user=teacher)
    assert t2.from_department == "B"          # snapshot reflects the first move
    moved = (await db.execute(select(User).where(User.id == staff.id))).scalar_one()
    assert moved.department == "C"
    hist = await list_transfers(staff_user_id=staff.id, db=db, current_user=teacher)
    assert len(hist) == 2                      # both moves logged


async def test_transfer_unknown_staff_404(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_transfer(TransferCreate(staff_user_id="nope", to_department="X"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_transfer_org_isolation(db, org, teacher):
    staff = await _staff(db, org, "Mine", department="A")
    await create_transfer(TransferCreate(staff_user_id=staff.id, to_department="B"), db=db, current_user=teacher)
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    rows = await list_transfers(staff_user_id=None, db=db, current_user=other)
    assert staff.id not in [t.staff_user_id for t in rows]


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_transfer_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
