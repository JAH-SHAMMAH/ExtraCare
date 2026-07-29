"""Pastoral Batch D-1: Hostel Setup config (managers / life grades / comment bank)
+ Hostel Students roster (over boarding_allocations) with multi-format import."""
from __future__ import annotations

import io
import uuid

import pytest

from app.models.user import User, UserStatus
from app.models.modules.pastoral import Hostel
from app.routers.modules.pastoral import (
    add_hostel_manager, list_hostel_managers, remove_hostel_manager,
    create_hostel_life_grade, list_hostel_life_grades, update_hostel_life_grade, delete_hostel_life_grade,
    create_hostel_comment, list_hostel_comment_bank, delete_hostel_comment,
    list_hostel_students, import_hostel_students, export_hostel_students,
)
from app.schemas.pastoral import (
    HostelManagerCreate, HostelLifeGradeCreate, HostelLifeGradeUpdate, HostelCommentBankCreate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Warden Ada",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _hostel(db, org, name="Green House") -> Hostel:
    h = Hostel(id=str(uuid.uuid4()), name=name, gender="boys", org_id=org.id)
    db.add(h)
    await db.commit()
    return h


class _Upload:
    """Minimal stand-in for FastAPI's UploadFile in a direct-call test."""
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    async def read(self) -> bytes:
        return self._content


async def test_hostel_setup_config_crud(db, org):
    admin = await _admin(db, org)
    h = await _hostel(db, org)

    # Managers
    m = await add_hostel_manager(payload=HostelManagerCreate(hostel_id=h.id, user_id=admin.id), db=db, current_user=admin)
    assert m.hostel_name == "Green House" and m.user_name == "Warden Ada"
    assert len(await list_hostel_managers(hostel_id=h.id, db=db, current_user=admin)) == 1
    await remove_hostel_manager(m.id, db=db, current_user=admin)
    assert len(await list_hostel_managers(hostel_id=None, db=db, current_user=admin)) == 0

    # Life grades (ordered by sort_order)
    await create_hostel_life_grade(payload=HostelLifeGradeCreate(name="Good", sort_order=2), db=db, current_user=admin)
    g1 = await create_hostel_life_grade(payload=HostelLifeGradeCreate(name="Excellent", sort_order=1), db=db, current_user=admin)
    grades = await list_hostel_life_grades(db=db, current_user=admin)
    assert [g.name for g in grades] == ["Excellent", "Good"]
    g1b = await update_hostel_life_grade(g1.id, HostelLifeGradeUpdate(is_active=False), db=db, current_user=admin)
    assert g1b.is_active is False
    await delete_hostel_life_grade(g1.id, db=db, current_user=admin)
    assert len(await list_hostel_life_grades(db=db, current_user=admin)) == 1

    # Comment bank
    c = await create_hostel_comment(payload=HostelCommentBankCreate(text="Keeps a tidy bed space.", category="Neatness"), db=db, current_user=admin)
    assert len(await list_hostel_comment_bank(db=db, current_user=admin)) == 1
    await delete_hostel_comment(c.id, db=db, current_user=admin)
    assert len(await list_hostel_comment_bank(db=db, current_user=admin)) == 0


async def test_hostel_manager_duplicate_guarded(db, org):
    from fastapi import HTTPException
    admin = await _admin(db, org)
    h = await _hostel(db, org, "Blue House")
    await add_hostel_manager(payload=HostelManagerCreate(hostel_id=h.id, user_id=admin.id), db=db, current_user=admin)
    with pytest.raises(HTTPException) as ei:
        await add_hostel_manager(payload=HostelManagerCreate(hostel_id=h.id, user_id=admin.id), db=db, current_user=admin)
    assert ei.value.status_code == 409


async def test_hostel_students_import_and_roster(db, org, student):
    admin = await _admin(db, org)
    h = await _hostel(db, org, "Red House")

    # Import by student name + hostel name.
    csv_bytes = ("student,hostel,room,bed\n"
                 f"{student.first_name} {student.last_name},Red House,R1,B2\n"
                 "Nobody Here,Red House,R1,B3\n"
                 f"{student.first_name} {student.last_name},Ghost House,R9,B9\n").encode()
    res = await import_hostel_students(file=_Upload("boarders.csv", csv_bytes), db=db, current_user=admin)
    assert res.imported == 1
    assert len(res.errors) == 2   # unknown student + unknown hostel

    rows = await list_hostel_students(hostel_id=None, search=None, db=db, current_user=admin)
    assert len(rows) == 1
    r = rows[0]
    assert r.hostel_name == "Red House" and r.room == "R1" and r.bed == "B2"
    assert r.admission_no == student.student_id

    # Filter by hostel + search.
    assert len(await list_hostel_students(hostel_id=h.id, search=student.first_name, db=db, current_user=admin)) == 1
    assert len(await list_hostel_students(hostel_id="does-not-exist", search=None, db=db, current_user=admin)) == 0

    resp = await export_hostel_students(hostel_id=None, search=None, db=db, current_user=admin)
    body = resp.body.decode()
    assert resp.media_type == "text/csv" and "Admission No" in body and student.student_id in body
