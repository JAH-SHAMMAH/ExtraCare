"""Tests for /hr/birthdays.

Merges two sources (HRProfile for staff, Student.date_of_birth for
students), filters by month, and surfaces a `is_today` flag. Today-first
sort must hold regardless of insert order.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.user import User, UserStatus
from app.models.hrm import HRProfile
from app.models.modules.school import Student
from app.routers.hr import upcoming_birthdays


pytestmark = pytest.mark.asyncio


async def _add_staff_with_dob(db, org, *, name: str, dob: date) -> User:
    u = User(
        id=str(uuid.uuid4()), email=f"{name.lower()}@example.com",
        full_name=name, status=UserStatus.ACTIVE, org_id=org.id,
    )
    db.add(u)
    await db.flush()
    p = HRProfile(
        id=str(uuid.uuid4()), user_id=u.id, org_id=org.id,
        date_of_birth=dob, memberships=[], next_of_kin={}, dependents=[],
    )
    db.add(p)
    await db.commit()
    return u


async def _add_student_with_dob(db, org, school_class, *, first: str, last: str, dob: date) -> Student:
    s = Student(
        id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:6]}",
        first_name=first, last_name=last, class_id=school_class.id,
        org_id=org.id, date_of_birth=dob,
    )
    db.add(s)
    await db.commit()
    return s


async def test_birthdays_returns_staff_and_students_in_month(db, org, teacher, school_class):
    today = date.today()
    m = today.month
    await _add_staff_with_dob(db, org, name="Staff One", dob=date(1990, m, 15))
    await _add_student_with_dob(db, org, school_class, first="Kid", last="One", dob=date(2012, m, 20))

    result = await upcoming_birthdays(month=m, db=db, current_user=teacher)
    names = {b.name for b in result}
    assert "Staff One" in names
    assert "Kid One" in names
    # Role is labelled correctly.
    roles = {b.name: b.role for b in result}
    assert roles["Staff One"] == "staff"
    assert roles["Kid One"] == "student"


async def test_birthdays_today_flag_and_sort(db, org, teacher, school_class):
    """Today's birthday must appear first with is_today=True."""
    today = date.today()
    # Pick two different days in today's month, including today.
    other_day = 1 if today.day != 1 else 28
    await _add_staff_with_dob(db, org, name="NotToday", dob=date(1985, today.month, other_day))
    await _add_staff_with_dob(db, org, name="TodayPerson", dob=date(1985, today.month, today.day))

    result = await upcoming_birthdays(month=None, db=db, current_user=teacher)
    assert result[0].name == "TodayPerson"
    assert result[0].is_today is True
    assert result[0].days_until == 0
    assert any(b.name == "NotToday" and b.is_today is False for b in result)


async def test_birthdays_defaults_to_current_month(db, org, teacher):
    """No month arg ⇒ current month window."""
    today = date.today()
    other_month = (today.month % 12) + 1
    await _add_staff_with_dob(db, org, name="ThisMonth", dob=date(1980, today.month, 10))
    await _add_staff_with_dob(db, org, name="OtherMonth", dob=date(1980, other_month, 10))

    result = await upcoming_birthdays(month=None, db=db, current_user=teacher)
    names = {b.name for b in result}
    assert "ThisMonth" in names
    assert "OtherMonth" not in names


async def test_birthdays_tenant_isolated(db, org, teacher, school_class):
    """Other-org staff birthdays must not leak into this org's list."""
    from app.models.organization import Organization, IndustryType
    other_org = Organization(
        id=str(uuid.uuid4()), name="Other Inc", slug=f"oth-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other_org)
    await db.commit()
    today = date.today()
    await _add_staff_with_dob(db, other_org, name="OtherOrgStaff", dob=date(1990, today.month, 5))
    await _add_staff_with_dob(db, org, name="OurStaff", dob=date(1990, today.month, 5))

    result = await upcoming_birthdays(month=None, db=db, current_user=teacher)
    names = {b.name for b in result}
    assert "OurStaff" in names
    assert "OtherOrgStaff" not in names


async def test_birthdays_ignores_profiles_without_dob(db, org, teacher):
    """A profile with date_of_birth=None must not appear."""
    u = User(
        id=str(uuid.uuid4()), email="nodob@example.com", full_name="No DOB",
        status=UserStatus.ACTIVE, org_id=org.id,
    )
    db.add(u)
    await db.flush()
    db.add(HRProfile(
        id=str(uuid.uuid4()), user_id=u.id, org_id=org.id,
        date_of_birth=None, memberships=[], next_of_kin={}, dependents=[],
    ))
    await db.commit()

    result = await upcoming_birthdays(month=None, db=db, current_user=teacher)
    assert all(b.name != "No DOB" for b in result)
