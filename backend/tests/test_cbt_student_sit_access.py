"""A student must be able to SIT the exam they were assigned.

Students hold `school:cbt:sit`, never `school:cbt:read` (the teacher/admin CBT
surface) — the role catalog narrowed them off it. Every endpoint on the sit path
was still gated on cbt:read, so a student could list their exams and then get a
403 the moment they opened one.

Two layers are covered here, because the bug lived in the first and the rest of
this suite only exercises the second:

  • the ROUTE gate — `dependencies=[...]`, which a direct handler call skips
    entirely. This is where the bug was, twice, so it is asserted directly.
  • the OWNERSHIP narrowing inside the handler — widening the scope must not let
    a student reach an exam that isn't theirs, or ever see an answer key.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.core.permissions import AnyPermissionChecker, PermissionChecker
from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import (
    CBTExam, CBTQuestion, ExamStatus, QuestionType, SchoolClass, Student,
)
from app.routers.modules.cbt import (
    router as cbt_router, get_exam, list_questions, start_attempt,
)

pytestmark = pytest.mark.asyncio

SIT = "school:cbt:sit"
READ = "school:cbt:read"

# The path a student walks: open the exam, load the paper, start, submit, then
# look at their attempts. All six must admit the scope students actually hold.
SIT_PATH_ROUTES = [
    ("/cbt/exams/{exam_id}", "GET"),
    ("/cbt/exams/{exam_id}/questions", "GET"),
    ("/cbt/exams/{exam_id}/attempts", "POST"),
    ("/cbt/attempts/{attempt_id}/submit", "POST"),
    ("/cbt/attempts", "GET"),
    ("/cbt/attempts/{attempt_id}", "GET"),
]

# Authoring / marking / admin surfaces. A sitting student must never reach these
# — this is the guard against "fixed the 403 by widening everything".
STAFF_ONLY_ROUTES = [
    ("/cbt/exams", "POST"),
    ("/cbt/exams/{exam_id}", "PATCH"),
    ("/cbt/exams/{exam_id}", "DELETE"),
    ("/cbt/exams/{exam_id}/questions", "POST"),
    ("/cbt/question-bank", "GET"),
    ("/cbt/question-bank", "POST"),
    ("/cbt/exams/{exam_id}/results", "GET"),
    ("/cbt/exams/{exam_id}/publish-results", "POST"),
    ("/cbt/attempts/{attempt_id}/review", "GET"),
    ("/cbt/attempts/{attempt_id}/remark", "POST"),
    ("/cbt/settings", "PUT"),
]


def _route_scopes(path: str, method: str) -> set[str]:
    """Scopes the ROUTE-level dependency admits — the layer direct handler calls
    bypass, and the layer both student-access bugs actually lived in."""
    for route in cbt_router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            scopes: set[str] = set()
            for dep in route.dependencies:
                checker = dep.dependency
                if isinstance(checker, AnyPermissionChecker):
                    scopes.update(checker.permissions)
                elif isinstance(checker, PermissionChecker):
                    scopes.add(checker.permission)
            return scopes
    raise AssertionError(f"route not registered: {method} {path}")


@pytest.mark.parametrize("path,method", SIT_PATH_ROUTES)
async def test_sit_path_routes_admit_the_student_scope(path, method):
    scopes = _route_scopes(path, method)
    assert SIT in scopes, f"{method} {path} locks students out of their own exam"
    assert READ in scopes, f"{method} {path} must keep working for teachers/admins"


@pytest.mark.parametrize("path,method", STAFF_ONLY_ROUTES)
async def test_authoring_routes_still_exclude_the_student_scope(path, method):
    assert SIT not in _route_scopes(path, method), f"{method} {path} is reachable by a student"


# ── ownership: the scope widened, the reach must not ──────────────────────────

async def _student(db, org, cls) -> tuple[Student, User]:
    email = f"pupil-{uuid.uuid4().hex[:6]}@example.com"
    role = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=email, full_name="Pupil",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    s = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:5]}", first_name="P",
                last_name="Q", email=email, user_id=u.id, class_id=cls.id, org_id=org.id)
    db.add_all([role, u, s])
    await db.commit()
    return s, u


async def _staff(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="manager", slug=f"m-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["manager"]), org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"staff-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Staff", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _class(db, org, name) -> SchoolClass:
    c = SchoolClass(id=str(uuid.uuid4()), name=name, level="Secondary", org_id=org.id)
    db.add(c)
    await db.commit()
    return c


async def _exam_with_question(db, org, cls, author) -> CBTExam:
    e = CBTExam(id=str(uuid.uuid4()), title="Quiz", status=ExamStatus.PUBLISHED,
                total_points=1.0, duration_minutes=60, class_id=cls.id,
                created_by=author.id, org_id=org.id)
    db.add(e)
    await db.flush()
    db.add(CBTQuestion(id=str(uuid.uuid4()), exam_id=e.id, question_text="2+2?",
                       question_type=QuestionType.MCQ, correct_answer="4", points=1.0,
                       position=0, org_id=org.id))
    await db.commit()
    return e


async def test_student_opens_their_own_classs_exam(db, org):
    staff = await _staff(db, org)
    cls = await _class(db, org, "JSS1 A")
    _, user = await _student(db, org, cls)
    exam = await _exam_with_question(db, org, cls, staff)

    assert user.has_permission(SIT) and not user.has_permission(READ)

    out = await get_exam(exam.id, db=db, current_user=user)
    assert out["id"] == exam.id

    qs = await list_questions(exam.id, include_answers=False, db=db, current_user=user)
    assert len(qs["items"]) == 1
    assert qs["items"][0]["question_text"] == "2+2?"


async def test_student_cannot_reach_another_classs_exam(db, org):
    """Widening the scope must not widen the reach: the list endpoint's `for_me`
    filter already denies this, and fetching by id must agree with it."""
    staff = await _staff(db, org)
    mine = await _class(db, org, "JSS1 A")
    theirs = await _class(db, org, "JSS1 B")
    _, user = await _student(db, org, mine)
    other_exam = await _exam_with_question(db, org, theirs, staff)

    for call in (
        lambda: get_exam(other_exam.id, db=db, current_user=user),
        lambda: list_questions(other_exam.id, include_answers=False, db=db, current_user=user),
        lambda: start_attempt(other_exam.id, student_id=None, db=db, current_user=user),
    ):
        with pytest.raises(HTTPException) as exc:
            await call()
        # 404, not 403 — an exam they may not see stays indistinguishable from one
        # that does not exist.
        assert exc.value.status_code == 404


async def test_sitting_student_never_receives_the_answer_key(db, org):
    """The reason the sit path may not simply inherit cbt:read."""
    staff = await _staff(db, org)
    cls = await _class(db, org, "JSS1 A")
    _, user = await _student(db, org, cls)
    exam = await _exam_with_question(db, org, cls, staff)

    qs = await list_questions(exam.id, include_answers=True, db=db, current_user=user)
    assert "correct_answer" not in qs["items"][0]

    staff_qs = await list_questions(exam.id, include_answers=True, db=db, current_user=staff)
    assert staff_qs["items"][0]["correct_answer"] == "4"


async def test_staff_reach_any_exam_regardless_of_class(db, org):
    """The sittability check keys off the student link; staff skip it entirely."""
    staff = await _staff(db, org)
    cls = await _class(db, org, "JSS1 A")
    exam = await _exam_with_question(db, org, cls, staff)

    out = await get_exam(exam.id, db=db, current_user=staff)
    assert out["id"] == exam.id


async def test_user_with_sit_but_no_student_record_is_refused(db, org):
    """A sit scope on an account with nothing linked resolves to no class, so it
    must fail closed rather than fall through to every exam."""
    staff = await _staff(db, org)
    cls = await _class(db, org, "JSS1 A")
    exam = await _exam_with_question(db, org, cls, staff)

    role = Role(id=str(uuid.uuid4()), name="student", slug=f"s-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["student"]), org_id=org.id, is_system=False)
    orphan = User(id=str(uuid.uuid4()), email=f"nolink-{uuid.uuid4().hex[:6]}@example.com",
                  full_name="No Link", status=UserStatus.ACTIVE, org_id=org.id)
    orphan.roles = [role]
    db.add_all([role, orphan])
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await get_exam(exam.id, db=db, current_user=orphan)
    assert exc.value.status_code == 404
