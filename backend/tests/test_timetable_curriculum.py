"""Tests for TimeTable Batch 3 — Curriculum CRUD, the simplified Time Tabler
generator, and the Subject Student Attendance filtered view."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models.user import User, UserStatus
from app.models.modules.school import SchoolClass, Subject, Student, AttendanceRecord, AttendanceStatus
from app.routers.modules.timetable import (
    create_period_group, generate_periods,
    create_curriculum, list_curriculum, update_curriculum, delete_curriculum,
    create_timetable_job, list_timetable_jobs, generate_timetable, delete_timetable_job,
    subject_student_attendance, list_schedules,
)
from app.schemas.timetable import (
    PeriodGroupCreate, PeriodGenerateRequest,
    CurriculumCreate, CurriculumUpdate, TimetableJobCreate,
)


pytestmark = pytest.mark.asyncio
YEAR = "2025/2026"


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com", full_name="Admin",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _class(db, org, name="Year 10A") -> SchoolClass:
    c = SchoolClass(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(c)
    await db.commit()
    return c


async def _subject(db, org, name="Maths") -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Curriculum ────────────────────────────────────────────────────────────────

async def test_curriculum_crud(db, org):
    admin = await _admin(db, org)
    cls = await _class(db, org)
    subj = await _subject(db, org, "English")
    c = await create_curriculum(CurriculumCreate(name="Scheme of Work T1", class_id=cls.id, subject_id=subj.id, academic_year=YEAR), db=db, current_user=admin)
    assert c["name"] == "Scheme of Work T1" and c["subject_name"] == "English"
    listing = await list_curriculum(class_id=cls.id, subject_id=None, academic_year=YEAR, db=db, current_user=admin)
    assert len(listing["items"]) == 1
    upd = await update_curriculum(c["id"], CurriculumUpdate(name="Scheme of Work (rev)"), db=db, current_user=admin)
    assert upd["name"] == "Scheme of Work (rev)"
    await delete_curriculum(c["id"], db=db, current_user=admin)
    assert len((await list_curriculum(class_id=cls.id, subject_id=None, academic_year=None, db=db, current_user=admin))["items"]) == 0


# ── Time Tabler ───────────────────────────────────────────────────────────────

async def test_timetabler_generate_round_robin(db, org):
    admin = await _admin(db, org)
    cls = await _class(db, org)
    await _subject(db, org, "Maths")
    await _subject(db, org, "English")
    pg = await create_period_group(PeriodGroupCreate(name="SEC"), db=db, current_user=admin)
    await generate_periods(PeriodGenerateRequest(period_group_id=pg["id"], academic_year=YEAR, days=[0], periods_per_day=4, start_time="08:00", minutes_per_period=40), db=db, current_user=admin)

    job = await create_timetable_job(TimetableJobCreate(title="Spring", period_group_id=pg["id"], academic_year=YEAR), db=db, current_user=admin)
    assert job["status"] == "draft"
    res = await generate_timetable(job["id"], db=db, current_user=admin)
    assert res.status == "processed"
    assert res.created == 4          # 1 class x 4 lesson periods
    # Schedules landed.
    assert len((await list_schedules(period_group_id=pg["id"], academic_year=YEAR, db=db, current_user=admin))["items"]) == 4


async def test_timetabler_fails_without_subjects(db, org):
    admin = await _admin(db, org)
    await _class(db, org)
    pg = await create_period_group(PeriodGroupCreate(name="G"), db=db, current_user=admin)
    await generate_periods(PeriodGenerateRequest(period_group_id=pg["id"], academic_year=YEAR, days=[0], periods_per_day=2, start_time="08:00", minutes_per_period=40), db=db, current_user=admin)
    job = await create_timetable_job(TimetableJobCreate(title="NoSubjects", period_group_id=pg["id"], academic_year=YEAR), db=db, current_user=admin)
    res = await generate_timetable(job["id"], db=db, current_user=admin)
    assert res.status == "failed" and res.created == 0
    # Job list reflects the failed status.
    jobs = await list_timetable_jobs(db=db, current_user=admin)
    assert jobs["items"][0]["status"] == "failed"
    await delete_timetable_job(job["id"], db=db, current_user=admin)
    assert len((await list_timetable_jobs(db=db, current_user=admin))["items"]) == 0


# ── Subject attendance ────────────────────────────────────────────────────────

async def test_subject_attendance_rollup(db, org):
    admin = await _admin(db, org)
    cls = await _class(db, org)
    s1 = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="Ada", last_name="O", class_id=cls.id, org_id=org.id)
    s2 = Student(id=str(uuid.uuid4()), student_id="S-2", first_name="Bem", last_name="K", class_id=cls.id, org_id=org.id)
    db.add_all([s1, s2])
    await db.commit()
    for d, st in [(date(2026, 3, 2), AttendanceStatus.PRESENT), (date(2026, 3, 3), AttendanceStatus.ABSENT), (date(2026, 3, 4), AttendanceStatus.LATE)]:
        db.add(AttendanceRecord(id=str(uuid.uuid4()), student_id=s1.id, class_id=cls.id, date=d, status=st, org_id=org.id))
    db.add(AttendanceRecord(id=str(uuid.uuid4()), student_id=s2.id, class_id=cls.id, date=date(2026, 3, 2), status=AttendanceStatus.PRESENT, org_id=org.id))
    await db.commit()

    res = await subject_student_attendance(class_id=cls.id, start_date=date(2026, 3, 1), end_date=date(2026, 3, 31), db=db, current_user=admin)
    assert res.days == 3
    by = {r.student_name: r for r in res.items}
    assert by["Ada O"].present == 1 and by["Ada O"].absent == 1 and by["Ada O"].late == 1 and by["Ada O"].total == 3
    assert by["Bem K"].present == 1 and by["Bem K"].total == 1
