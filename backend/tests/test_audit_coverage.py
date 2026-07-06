"""Priority 1 — audit-coverage tests.

Verify that the academic-core mutations in the school router write an immutable
AuditLog row with the right action, resource_type, severity and payload. Handlers
are invoked directly (conftest convention) with `request` omitted → the audit row
is still written (just without client IP, which only the HTTP stack supplies).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog, AuditAction
from app.models.modules.school import Subject
from app.routers.modules.school import (
    create_student, update_student, delete_student,
    mark_attendance, submit_grades,
    create_teacher, delete_teacher,
    create_lesson, delete_lesson, create_timetable_slot,
)
from app.routers.modules.cbt import create_exam, delete_exam, add_question
from app.routers.modules.behaviour import create_record, delete_record
from app.routers.modules.tuckshop import create_product, record_purchase
from app.routers.modules.classroom import create_assignment, create_submission, grade_submission
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.teacher import TeacherCreate
from app.schemas.school_experience import (
    ExamCreate, QuestionCreate, BehaviourCreate, TuckshopProductCreate,
    TuckshopPurchaseCreate, AssignmentCreate, SubmissionCreate, SubmissionGrade,
)

pytestmark = pytest.mark.asyncio


async def _make_subject(db, org, teacher):
    import uuid as _uuid
    s = Subject(id=str(_uuid.uuid4()), name="Mathematics", org_id=org.id, teacher_id=teacher.id)
    db.add(s)
    await db.flush()
    return s


async def _audits(db, resource_type=None, action=None):
    rows = (await db.execute(select(AuditLog))).scalars().all()
    if resource_type is not None:
        rows = [r for r in rows if r.resource_type == resource_type]
    if action is not None:
        rows = [r for r in rows if r.action == action]
    return rows


async def test_create_student_writes_audit(db, org, teacher, school_class):
    data = StudentCreate(
        student_id="A-1", first_name="Ada", last_name="Okafor",
        email="ada.audit@example.com", class_id=school_class.id,
        date_of_birth=date(2010, 3, 4),
    )
    res = await create_student(data=data, db=db, current_user=teacher)

    rows = await _audits(db, resource_type="Student", action=AuditAction.RECORD_CREATED)
    assert len(rows) == 1
    a = rows[0]
    assert a.resource_id == res["id"]
    assert a.actor_id == teacher.id
    assert a.actor_email == teacher.email
    assert a.severity == "info"
    assert a.new_values.get("student_id") == "A-1"


async def test_update_student_writes_audit(db, org, teacher, student):
    await update_student(
        id=student.id, data=StudentUpdate(first_name="Updated"),
        db=db, current_user=teacher,
    )
    rows = await _audits(db, resource_type="Student", action=AuditAction.RECORD_UPDATED)
    assert len(rows) == 1
    assert rows[0].resource_id == student.id
    assert rows[0].new_values.get("first_name") == "Updated"
    assert rows[0].severity == "info"


async def test_delete_student_writes_warning_audit(db, org, teacher, student):
    await delete_student(id=student.id, db=db, current_user=teacher)
    rows = await _audits(db, resource_type="Student", action=AuditAction.RECORD_DELETED)
    assert len(rows) == 1
    assert rows[0].severity == "warning"
    assert rows[0].resource_id == student.id


async def test_mark_attendance_writes_audit(db, org, teacher, student, school_class):
    await mark_attendance(
        records=[{"student_id": student.id, "class_id": school_class.id, "status": "present"}],
        attendance_date=date(2026, 6, 1), db=db, current_user=teacher,
    )
    rows = await _audits(db, resource_type="AttendanceRecord")
    assert len(rows) == 1
    assert rows[0].action == AuditAction.RECORD_CREATED
    assert rows[0].metadata_["count"] == 1
    assert rows[0].metadata_["date"] == "2026-06-01"


async def test_submit_grades_writes_warning_audit(db, org, teacher, student):
    await submit_grades(
        grades=[{"student_id": student.id, "subject_id": "subj-1", "score": 80, "term": "T1"}],
        db=db, current_user=teacher,
    )
    rows = await _audits(db, resource_type="Grade")
    assert len(rows) == 1
    assert rows[0].action == AuditAction.RECORD_CREATED
    assert rows[0].severity == "warning"
    assert rows[0].metadata_["count"] == 1


async def test_failed_create_writes_no_audit(db, org, teacher):
    """A create that raises before completion must NOT leave an audit row
    (the operation + its log share the caller's transaction)."""
    bad = StudentCreate(
        student_id="A-2", first_name="X", last_name="Y",
        class_id="does-not-exist",  # cross-tenant / missing FK → 404 before audit
    )
    with pytest.raises(Exception):
        await create_student(data=bad, db=db, current_user=teacher)
    assert await _audits(db, resource_type="Student") == []


# ── Part B: teachers / lessons / timetable / CBT / behaviour / tuckshop ───────

async def test_teacher_create_and_delete_audit(db, org, teacher):
    t = await create_teacher(
        data=TeacherCreate(first_name="New", last_name="Teach", email="newteach@example.com"),
        db=db, current_user=teacher,
    )
    created = await _audits(db, resource_type="Teacher", action=AuditAction.RECORD_CREATED)
    assert len(created) == 1 and created[0].severity == "info"

    await delete_teacher(id=t["id"], db=db, current_user=teacher)
    deleted = await _audits(db, resource_type="Teacher", action=AuditAction.RECORD_DELETED)
    assert len(deleted) == 1 and deleted[0].severity == "warning"


async def test_lesson_create_and_delete_audit(db, org, teacher, school_class):
    # create_lesson calls _is_admin_role(current_user) which reads user.roles.
    # The HTTP stack selectin-loads roles via get_current_user; a direct-call
    # test must load them first to avoid a lazy-load outside the async greenlet.
    await db.refresh(teacher, attribute_names=["roles"])
    subj = await _make_subject(db, org, teacher)
    plan = await create_lesson(
        payload={"title": "Algebra", "class_id": school_class.id,
                 "subject_id": subj.id, "lesson_date": "2026-06-01"},
        db=db, current_user=teacher,
    )
    created = await _audits(db, resource_type="LessonPlan", action=AuditAction.RECORD_CREATED)
    assert len(created) == 1 and created[0].severity == "info"

    await delete_lesson(plan_id=plan["id"], db=db, current_user=teacher)
    deleted = await _audits(db, resource_type="LessonPlan", action=AuditAction.RECORD_DELETED)
    assert len(deleted) == 1 and deleted[0].severity == "warning"


async def test_timetable_create_audit(db, org, teacher, school_class):
    subj = await _make_subject(db, org, teacher)
    await create_timetable_slot(
        data={"class_id": school_class.id, "subject_id": subj.id, "teacher_id": teacher.id,
              "day_of_week": 1, "start_time": "09:00", "end_time": "10:00"},
        db=db, current_user=teacher,
    )
    rows = await _audits(db, resource_type="Timetable", action=AuditAction.RECORD_CREATED)
    assert len(rows) == 1


async def test_cbt_exam_question_audit(db, org, teacher):
    exam = await create_exam(payload=ExamCreate(title="Midterm"), db=db, current_user=teacher)
    assert len(await _audits(db, resource_type="CBTExam", action=AuditAction.RECORD_CREATED)) == 1

    await add_question(
        exam_id=exam["id"], payload=QuestionCreate(question_text="2+2?", points=1.0),
        db=db, current_user=teacher,
    )
    assert len(await _audits(db, resource_type="CBTQuestion", action=AuditAction.RECORD_CREATED)) == 1

    await delete_exam(exam_id=exam["id"], db=db, current_user=teacher)
    deleted = await _audits(db, resource_type="CBTExam", action=AuditAction.RECORD_DELETED)
    assert len(deleted) == 1 and deleted[0].severity == "warning"


async def test_behaviour_create_and_delete_audit(db, org, teacher, student):
    from datetime import date as _date
    rec = await create_record(
        payload=BehaviourCreate(student_id=student.id, description="Helped a peer",
                                type="positive", points=5, incident_date=_date(2026, 6, 1)),
        db=db, current_user=teacher,
    )
    assert len(await _audits(db, resource_type="BehaviourRecord", action=AuditAction.RECORD_CREATED)) == 1

    await delete_record(record_id=rec["id"], db=db, current_user=teacher)
    deleted = await _audits(db, resource_type="BehaviourRecord", action=AuditAction.RECORD_DELETED)
    assert len(deleted) == 1 and deleted[0].severity == "warning"


async def test_tuckshop_product_and_purchase_audit(db, org, teacher, student):
    prod = await create_product(
        payload=TuckshopProductCreate(name="Juice", price=2.5, stock=100),
        db=db, current_user=teacher,
    )
    assert len(await _audits(db, resource_type="TuckshopProduct", action=AuditAction.RECORD_CREATED)) == 1

    await record_purchase(
        payload=TuckshopPurchaseCreate(student_id=student.id, product_id=prod["id"], quantity=2),
        db=db, current_user=teacher,
    )
    pur = await _audits(db, resource_type="TuckshopPurchase")
    assert len(pur) == 1
    assert pur[0].severity == "warning"
    assert pur[0].metadata_["quantity"] == 2


async def test_classroom_assignment_and_grade_audit(db, org, teacher, school_class, student):
    a = await create_assignment(
        payload=AssignmentCreate(title="Essay", class_id=school_class.id),
        db=db, current_user=teacher,
    )
    assert len(await _audits(db, resource_type="Assignment", action=AuditAction.RECORD_CREATED)) == 1

    sub = await create_submission(
        payload=SubmissionCreate(assignment_id=a["id"], student_id=student.id, content="My essay"),
        db=db, current_user=teacher,
    )
    # create_submission is intentionally NOT audited (student self-service) —
    # confirm no row was written for the submission create.
    assert await _audits(db, resource_type="AssignmentSubmission", action=AuditAction.RECORD_CREATED) == []

    await grade_submission(
        submission_id=sub["id"], payload=SubmissionGrade(score=85.0, feedback="Good work"),
        db=db, current_user=teacher,
    )
    graded = await _audits(db, resource_type="AssignmentSubmission", action=AuditAction.RECORD_UPDATED)
    assert len(graded) == 1
    assert graded[0].severity == "warning"
    assert graded[0].metadata_["score"] == 85.0
