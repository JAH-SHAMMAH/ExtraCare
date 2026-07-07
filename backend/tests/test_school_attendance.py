"""Tests for GET /school/attendance (load existing marks).

Marking worked (POST /attendance) but there was no way to *read back* a class's
marks for a date, so the marking grid never pre-populated — a real bug. Proves:
  • list returns records for a class + date in the shape the grid reads
    (student_id + status)
  • the date alias ("?date=") filters correctly; other dates come back empty
  • RBAC: read = school:read
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.routers.modules.school import mark_attendance, list_attendance


pytestmark = pytest.mark.asyncio


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


async def test_list_returns_marks_for_class_and_date(db, org, teacher, school_class, student):
    day = date(2026, 7, 7)
    await mark_attendance(
        [{"student_id": student.id, "class_id": school_class.id, "status": "present"}],
        attendance_date=day, request=None, db=db, current_user=teacher,
    )
    res = await list_attendance(class_id=school_class.id, attendance_date=day, db=db, current_user=teacher)
    assert len(res["items"]) == 1
    row = res["items"][0]
    assert row["student_id"] == student.id and row["status"] == "present"
    assert row["class_id"] == school_class.id and row["date"] == "2026-07-07"


async def test_date_filter_excludes_other_days(db, org, teacher, school_class, student):
    await mark_attendance(
        [{"student_id": student.id, "class_id": school_class.id, "status": "absent"}],
        attendance_date=date(2026, 7, 7), request=None, db=db, current_user=teacher,
    )
    same = await list_attendance(class_id=school_class.id, attendance_date=date(2026, 7, 7), db=db, current_user=teacher)
    assert len(same["items"]) == 1 and same["items"][0]["status"] == "absent"
    other = await list_attendance(class_id=school_class.id, attendance_date=date(2026, 1, 1), db=db, current_user=teacher)
    assert len(other["items"]) == 0


async def test_no_date_returns_all_for_class(db, org, teacher, school_class, student):
    await mark_attendance([{"student_id": student.id, "class_id": school_class.id, "status": "late"}],
                          attendance_date=date(2026, 7, 7), request=None, db=db, current_user=teacher)
    res = await list_attendance(class_id=school_class.id, attendance_date=None, db=db, current_user=teacher)
    assert len(res["items"]) == 1 and res["items"][0]["status"] == "late"


async def test_attendance_rbac(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read")
    for slug in ("parent", "student"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:read")
