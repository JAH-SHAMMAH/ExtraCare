"""Tests for /hr/overview — the headline metrics block.

All five numbers must come from real tables:
  • total_active_staff  — Users with status ACTIVE, scoped by org
  • total_profiles      — HRProfile rows, scoped by org
  • staff_per_department — Users grouped by department ("Unassigned" fallback)
  • gender_distribution — HRProfile.gender ("Unspecified" fallback)
  • age_distribution    — 5 buckets computed in Python from HRProfile DOB
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.user import User, UserStatus
from app.models.hrm import HRProfile
from app.routers.hr import hr_overview


pytestmark = pytest.mark.asyncio


async def _add_user(db, org, *, email: str, dept: str | None = None,
                     status: UserStatus = UserStatus.ACTIVE) -> User:
    u = User(
        id=str(uuid.uuid4()), email=email, full_name=email.split("@")[0],
        status=status, org_id=org.id, department=dept,
    )
    db.add(u)
    await db.flush()
    return u


async def _add_profile(db, org, user, *, gender: str | None = None,
                        dob: date | None = None) -> HRProfile:
    p = HRProfile(
        id=str(uuid.uuid4()), user_id=user.id, org_id=org.id,
        gender=gender, date_of_birth=dob,
        memberships=[], next_of_kin={}, dependents=[],
    )
    db.add(p)
    await db.flush()
    return p


async def test_overview_empty_org(db, org, teacher):
    """Fresh org (only the fixture teacher) returns zero-but-honest metrics."""
    result = await hr_overview(db=db, current_user=teacher)
    assert result.total_active_staff >= 1  # teacher fixture
    assert result.total_profiles == 0
    # Age buckets always enumerated even when empty — chart needs labels.
    labels = [b.label for b in result.age_distribution]
    assert labels == ["Under 25", "25-34", "35-44", "45-54", "55+"]
    assert all(b.count == 0 for b in result.age_distribution)


async def test_overview_counts_active_only(db, org, teacher):
    await _add_user(db, org, email="a@x.com", status=UserStatus.ACTIVE)
    await _add_user(db, org, email="b@x.com", status=UserStatus.SUSPENDED)
    await db.commit()

    result = await hr_overview(db=db, current_user=teacher)
    # teacher + 'a' = 2 active; suspended 'b' excluded.
    assert result.total_active_staff == 2


async def test_overview_department_breakdown(db, org, teacher):
    await _add_user(db, org, email="eng1@x.com", dept="Engineering")
    await _add_user(db, org, email="eng2@x.com", dept="Engineering")
    await _add_user(db, org, email="hr1@x.com", dept="HR")
    await _add_user(db, org, email="no-dept@x.com", dept=None)
    await db.commit()

    result = await hr_overview(db=db, current_user=teacher)
    deptmap = {d.department: d.count for d in result.staff_per_department}
    assert deptmap.get("Engineering") == 2
    assert deptmap.get("HR") == 1
    # teacher fixture has no department, joined with the null entry → Unassigned
    assert deptmap.get("Unassigned", 0) >= 1


async def test_overview_gender_distribution(db, org, teacher):
    u1 = await _add_user(db, org, email="u1@x.com")
    u2 = await _add_user(db, org, email="u2@x.com")
    u3 = await _add_user(db, org, email="u3@x.com")
    await _add_profile(db, org, u1, gender="Male")
    await _add_profile(db, org, u2, gender="Female")
    await _add_profile(db, org, u3, gender=None)  # → Unspecified
    await db.commit()

    result = await hr_overview(db=db, current_user=teacher)
    gmap = {g.label: g.count for g in result.gender_distribution}
    assert gmap.get("Male") == 1
    assert gmap.get("Female") == 1
    assert gmap.get("Unspecified") == 1


async def test_overview_age_buckets(db, org, teacher):
    today = date.today()

    def dob_for_age(age: int) -> date:
        # Use July 1 to avoid "not yet had birthday this year" drift.
        return date(today.year - age, 7, 1) if today.month > 7 else date(today.year - age - 1, 7, 1)

    u_young = await _add_user(db, org, email="y@x.com")
    u_mid = await _add_user(db, org, email="m@x.com")
    u_old = await _add_user(db, org, email="o@x.com")
    await _add_profile(db, org, u_young, dob=dob_for_age(22))
    await _add_profile(db, org, u_mid, dob=dob_for_age(40))
    await _add_profile(db, org, u_old, dob=dob_for_age(60))
    await db.commit()

    result = await hr_overview(db=db, current_user=teacher)
    agemap = {b.label: b.count for b in result.age_distribution}
    assert agemap["Under 25"] == 1
    assert agemap["35-44"] == 1
    assert agemap["55+"] == 1
    # Unrepresented buckets stay at 0, not missing.
    assert agemap["25-34"] == 0
    assert agemap["45-54"] == 0


async def test_overview_tenant_isolated(db, org, teacher):
    """Another org's users/profiles must not contribute to this org's numbers."""
    from app.models.organization import Organization, IndustryType
    other_org = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"oth-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other_org)
    await db.commit()
    u = User(
        id=str(uuid.uuid4()), email="leak@other.com", full_name="Leak",
        status=UserStatus.ACTIVE, org_id=other_org.id, department="SecretOps",
    )
    db.add(u)
    await db.flush()
    db.add(HRProfile(
        id=str(uuid.uuid4()), user_id=u.id, org_id=other_org.id,
        gender="Male", memberships=[], next_of_kin={}, dependents=[],
    ))
    await db.commit()

    result = await hr_overview(db=db, current_user=teacher)
    depts = {d.department for d in result.staff_per_department}
    assert "SecretOps" not in depts
    assert result.total_profiles == 0  # the other org's profile excluded
