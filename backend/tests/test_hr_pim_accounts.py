"""Tests for PIM › Staff Account Numbers.

Reuses HRProfile bank fields. The list is the payroll population (all employees —
students/parents excluded), and updating creates the profile row on demand. Gated
hr:write.
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.hrm import HRProfile
from app.core.permissions import PermissionChecker
from app.routers.hr_pim import list_accounts, update_account
from app.schemas.hr_pim import AccountUpdate

pytestmark = pytest.mark.asyncio


async def _role(db, org, slug) -> Role:
    r = Role(id=str(uuid.uuid4()), name=slug.title(), slug=slug, permissions=[], org_id=org.id, is_system=True)
    db.add(r)
    await db.commit()
    return r


async def _user(db, org, name, role: Role | None = None) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{name.replace(' ', '.').lower()}-{uuid.uuid4().hex[:5]}@example.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    if role:
        u.roles = [role]
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


async def test_accounts_list_excludes_students_and_parents(db, org, teacher):
    student_role = await _role(db, org, "student")
    parent_role = await _role(db, org, "parent")
    emp = await _user(db, org, "Employee One")
    await _user(db, org, "Student Kid", role=student_role)
    await _user(db, org, "Parent Guardian", role=parent_role)

    rows = await list_accounts(search=None, db=db, current_user=teacher)
    names = {r.full_name for r in rows}
    assert "Employee One" in names
    assert "Student Kid" not in names and "Parent Guardian" not in names


async def test_update_account_creates_profile_and_reflects(db, org, teacher):
    emp = await _user(db, org, "Bank Owner")
    updated = await update_account(emp.id, AccountUpdate(bank_name="GTBank", bank_account_name="Bank Owner", bank_account_number="0123456789"),
                                   db=db, current_user=teacher)
    assert updated.bank_account_number == "0123456789" and updated.bank_name == "GTBank"
    # Persisted on a real HRProfile row…
    prof = (await db.execute(select(HRProfile).where(HRProfile.user_id == emp.id))).scalar_one_or_none()
    assert prof is not None and prof.bank_account_number == "0123456789"
    # …and visible in the list.
    rows = await list_accounts(search=None, db=db, current_user=teacher)
    row = next(r for r in rows if r.user_id == emp.id)
    assert row.bank_name == "GTBank"


async def test_update_account_search_and_404(db, org, teacher):
    emp = await _user(db, org, "Searchable Person")
    await update_account(emp.id, AccountUpdate(bank_name="Zenith"), db=db, current_user=teacher)
    hit = await list_accounts(search="Searchable", db=db, current_user=teacher)
    assert any(r.user_id == emp.id for r in hit)
    with pytest.raises(HTTPException) as exc:
        await update_account("nope", AccountUpdate(bank_name="X"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_accounts_org_isolation(db, org, teacher):
    emp = await _user(db, org, "My Org Emp")
    other = SimpleNamespace(org_id=str(uuid.uuid4()))
    rows = await list_accounts(search=None, db=db, current_user=other)
    assert emp.id not in [r.user_id for r in rows]
    with pytest.raises(HTTPException) as exc:
        await update_account(emp.id, AccountUpdate(bank_name="X"), db=db, current_user=other)
    assert exc.value.status_code == 404


async def _run_gate(user, org, db):
    checker = PermissionChecker("hr:write")
    request = SimpleNamespace(state=SimpleNamespace(org=org, org_id=org.id))
    return await checker(request=request, current_user=user, db=db)


async def test_accounts_rbac(db, org):
    tchr = await _preset_user(db, org, "teacher")
    assert not tchr.has_permission("hr:write")
    with pytest.raises(HTTPException) as exc:
        await _run_gate(tchr, org, db)
    assert exc.value.status_code == 403
    for slug in ("org_admin", "manager"):
        u = await _preset_user(db, org, slug)
        assert (await _run_gate(u, org, db)).id == u.id
