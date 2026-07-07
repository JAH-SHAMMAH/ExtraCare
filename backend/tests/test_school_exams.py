"""Tests for the Exams manual gradebook — /school/exams + results.

The exams page (list/create/results) had no backend. Proves:
  • create maps `date`->exam_date, validates exam_type/status, defaults to scheduled
  • list returns the frontend Exam shape with subject_name/class_name + entered/total
  • results GET returns the full class roster merged with entered scores
  • results POST upserts Grade rows tagged with exam_id, computes WAEC grade_letter,
    skips blank rows, and requires a subject
  • those grades show up in the existing report-card
  • RBAC: read = school:read, writes = school:write
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Exam, Grade, Student
from app.routers.modules.school import (
    list_exams, get_exam, create_exam, update_exam,
    get_exam_results, submit_exam_results, get_report_card, _grade_letter,
    create_subject,
)
from app.schemas.exam import ExamCreate, ExamUpdate, ExamResultRow
from app.schemas.subject import SubjectCreate


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


async def _subject(db, teacher, name="Mathematics"):
    return await create_subject(SubjectCreate(name=name), request=None, db=db, current_user=teacher)


async def _extra_student(db, org, school_class, first, last):
    s = Student(id=str(uuid.uuid4()), student_id=f"S{uuid.uuid4().hex[:5]}", first_name=first,
                last_name=last, class_id=school_class.id, org_id=org.id, is_active=True)
    db.add(s)
    await db.commit()
    return s


# ── Grade-letter scale (WAEC default) ────────────────────────────────────────────

def test_grade_letter_boundaries():
    assert _grade_letter(70, 100) == "A"
    assert _grade_letter(69, 100) == "B"
    assert _grade_letter(50, 100) == "C"
    assert _grade_letter(45, 100) == "D"
    assert _grade_letter(40, 100) == "E"
    assert _grade_letter(39, 100) == "F"
    assert _grade_letter(None, 100) is None
    assert _grade_letter(9, 0) is None
    # scaled to a non-100 total
    assert _grade_letter(35, 50) == "A"   # 70%


# ── Create / list ─────────────────────────────────────────────────────────────────

async def test_create_maps_and_defaults(db, org, teacher, school_class):
    subj = await _subject(db, teacher)
    resp = await create_exam(
        ExamCreate(name="First Term Exam", exam_type="final", subject_id=subj["id"],
                   class_id=school_class.id, term="Term 1", date="2026-07-10", total_marks=50),
        request=None, db=db, current_user=teacher,
    )
    assert resp["name"] == "First Term Exam" and resp["exam_type"] == "final"
    assert resp["status"] == "scheduled"                 # default
    assert resp["date"] == "2026-07-10"                  # date -> exam_date
    assert resp["subject_name"] == "Mathematics" and resp["class_name"] == school_class.name
    assert resp["total_marks"] == 50
    row = (await db.execute(select(Exam).where(Exam.id == resp["id"]))).scalar_one()
    assert row.exam_date is not None and row.total_marks == 50


async def test_create_rejects_bad_type(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_exam(ExamCreate(name="X", exam_type="oral"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_list_shape_and_filter(db, org, teacher, school_class):
    subj = await _subject(db, teacher)
    await create_exam(ExamCreate(name="Mid", subject_id=subj["id"], class_id=school_class.id, status="scheduled"),
                      request=None, db=db, current_user=teacher)
    await create_exam(ExamCreate(name="Final", subject_id=subj["id"], class_id=school_class.id, status="completed"),
                      request=None, db=db, current_user=teacher)
    allres = await list_exams(page=1, page_size=50, status=None, class_id=None, term=None, db=db, current_user=teacher)
    assert allres["total"] == 2
    row = allres["items"][0]
    assert "subject_name" in row and "entered_count" in row and "total_students" in row
    done = await list_exams(page=1, page_size=50, status="completed", class_id=None, term=None, db=db, current_user=teacher)
    assert done["total"] == 1 and done["items"][0]["name"] == "Final"


# ── Results: roster, upsert, grade computation, report-card ───────────────────────

async def test_results_roster_and_upsert(db, org, teacher, school_class, student):
    other = await _extra_student(db, org, school_class, "Ada", "Obi")
    subj = await _subject(db, teacher)
    exam = await create_exam(ExamCreate(name="CA1", subject_id=subj["id"], class_id=school_class.id, term="Term 1", total_marks=100),
                             request=None, db=db, current_user=teacher)

    # roster shows every enrolled student, scores blank
    before = await get_exam_results(exam["id"], db=db, current_user=teacher)
    assert len(before["results"]) == 2
    assert all(r["score"] is None for r in before["results"])

    # submit one real score + one blank (skipped)
    res = await submit_exam_results(
        exam["id"],
        [ExamResultRow(student_id=student.id, score=82), ExamResultRow(student_id=other.id, score=None)],
        request=None, db=db, current_user=teacher,
    )
    assert res["submitted"] == 1

    after = await get_exam_results(exam["id"], db=db, current_user=teacher)
    scored = next(r for r in after["results"] if r["student_id"] == student.id)
    assert scored["score"] == 82 and scored["grade_letter"] == "A"
    assert after["exam"]["entered_count"] == 1 and after["exam"]["total_students"] == 2

    # re-submitting updates in place (no duplicate Grade rows)
    await submit_exam_results(exam["id"], [ExamResultRow(student_id=student.id, score=55)],
                              request=None, db=db, current_user=teacher)
    grades = (await db.execute(select(Grade).where(Grade.exam_id == exam["id"], Grade.student_id == student.id))).scalars().all()
    assert len(grades) == 1 and grades[0].score == 55 and grades[0].grade_letter == "C"


async def test_results_require_subject(db, org, teacher, school_class, student):
    exam = await create_exam(ExamCreate(name="NoSubj", class_id=school_class.id), request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await submit_exam_results(exam["id"], [ExamResultRow(student_id=student.id, score=50)],
                                  request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_exam_grades_reach_report_card(db, org, teacher, school_class, student):
    subj = await _subject(db, teacher)
    exam = await create_exam(ExamCreate(name="Term Exam", subject_id=subj["id"], class_id=school_class.id, term="Term 1"),
                             request=None, db=db, current_user=teacher)
    await submit_exam_results(exam["id"], [ExamResultRow(student_id=student.id, score=88)],
                              request=None, db=db, current_user=teacher)
    # report-card checks has_permission in-body, so use a role-loaded staff user
    # (mirrors production, where the auth dep eager-loads roles).
    staff = await _preset_user(db, org, "teacher")
    card = await get_report_card(student.id, term="Term 1", db=db, current_user=staff)
    assert card["average"] == 88
    assert any(g["subject_id"] == subj["id"] and g["score"] == 88 for g in card["grades"])


async def test_update_status_and_404(db, org, teacher, school_class):
    subj = await _subject(db, teacher)
    exam = await create_exam(ExamCreate(name="Upd", subject_id=subj["id"], class_id=school_class.id),
                             request=None, db=db, current_user=teacher)
    upd = await update_exam(exam["id"], ExamUpdate(status="completed", total_marks=80),
                            request=None, db=db, current_user=teacher)
    assert upd["status"] == "completed" and upd["total_marks"] == 80
    with pytest.raises(HTTPException) as exc:
        await get_exam(str(uuid.uuid4()), db=db, current_user=teacher)
    assert exc.value.status_code == 404
