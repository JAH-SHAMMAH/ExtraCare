"""Tests for /hr/me and /hr/profiles/{user_id}.

Covers the two regressions that matter most:
  • Blank-string coercion — browsers submit '' for unfilled optional
    fields; these must land as None, not hit SQLAlchemy Date/Float as
    empty strings.
  • Lazy profile creation — first GET on /hr/me must insert a row so
    existing orgs aren't forced to migrate before the UI works.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.hrm import HRProfile
from app.routers.hr import (
    get_my_profile, update_my_profile, get_user_profile,
)
from app.schemas.hrm import HRProfileUpdate


pytestmark = pytest.mark.asyncio


async def test_get_me_creates_blank_profile(db, teacher):
    """First hit on /hr/me should lazy-create the HRProfile row."""
    result = await get_my_profile(db=db, current_user=teacher)
    assert result.user_id == teacher.id
    assert result.org_id == teacher.org_id
    assert result.email == teacher.email
    assert result.memberships == []
    assert result.next_of_kin == {}
    assert result.dependents == []


async def test_get_me_is_idempotent(db, teacher):
    """Calling GET /hr/me twice must not create a duplicate row."""
    await get_my_profile(db=db, current_user=teacher)
    await get_my_profile(db=db, current_user=teacher)

    from sqlalchemy import select, func
    count = (await db.execute(
        select(func.count()).select_from(HRProfile).where(HRProfile.user_id == teacher.id)
    )).scalar()
    assert count == 1


async def test_patch_me_updates_fields(db, teacher):
    data = HRProfileUpdate(
        title="Ms",
        first_name="Amara",
        surname="Eze",
        staff_id="EMP-001",
        gender="Female",
        nationality="Nigerian",
        date_of_birth=date(1990, 6, 15),
        hire_date=date(2022, 1, 10),
        salary=450000.0,
        salary_currency="NGN",
        bank_name="GTBank",
        bank_account_number="0123456789",
    )
    result = await update_my_profile(data=data, db=db, current_user=teacher)
    assert result.first_name == "Amara"
    assert result.staff_id == "EMP-001"
    assert result.salary == 450000.0
    assert result.bank_account_number == "0123456789"  # owner sees full number


async def test_patch_me_coerces_empty_strings(db, teacher):
    """Form submissions with '' for optional fields must become None, not
    reach SQLAlchemy Date/Float columns as empty strings."""
    data = HRProfileUpdate.model_validate({
        "title": "",
        "first_name": "",
        "date_of_birth": "",
        "hire_date": "",
        "salary": "",
        "national_id_expiry": "",
        "bank_account_number": "",
    })
    assert data.title is None
    assert data.date_of_birth is None
    assert data.salary is None
    assert data.national_id_expiry is None

    result = await update_my_profile(data=data, db=db, current_user=teacher)
    assert result.title is None
    assert result.date_of_birth is None


async def test_patch_me_persists_json_fields(db, teacher):
    """Nested JSON updates must stick — flag_modified required for SQLA."""
    from sqlalchemy import select

    data = HRProfileUpdate(
        memberships=[{"body": "ICAN", "membership_number": "A123", "expires_at": "2027-01-01"}],
        next_of_kin={"name": "Chidi Eze", "relationship": "Spouse", "phone": "+2348000000"},
        dependents=[{"name": "Zara", "relationship": "Daughter", "date_of_birth": "2015-04-01"}],
    )
    await update_my_profile(data=data, db=db, current_user=teacher)
    await db.commit()

    row = (await db.execute(
        select(HRProfile).where(HRProfile.user_id == teacher.id)
    )).scalar_one()
    assert row.memberships[0]["body"] == "ICAN"
    assert row.next_of_kin["relationship"] == "Spouse"
    assert row.dependents[0]["name"] == "Zara"


async def test_admin_get_profile_same_org(db, org, teacher, unlinked_user):
    """Admin can view another user's profile in the same org."""
    result = await get_user_profile(
        user_id=unlinked_user.id, db=db, current_user=teacher,
    )
    assert result.user_id == unlinked_user.id
    assert result.org_id == org.id


async def test_admin_get_profile_cross_org_404(db, teacher):
    """Cross-org lookup must 404 — tenant isolation is absolute."""
    from app.models.user import User, UserStatus
    from app.models.organization import Organization, IndustryType

    other_org = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"other-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other_org)
    await db.commit()
    other_user = User(
        id=str(uuid.uuid4()), email="other@example.com", full_name="Other",
        status=UserStatus.ACTIVE, org_id=other_org.id,
    )
    db.add(other_user)
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await get_user_profile(user_id=other_user.id, db=db, current_user=teacher)
    assert exc.value.status_code == 404
    assert "User not found" in exc.value.detail


async def test_admin_get_unknown_user_404(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await get_user_profile(user_id="does-not-exist", db=db, current_user=teacher)
    assert exc.value.status_code == 404
