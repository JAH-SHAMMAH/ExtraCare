"""Entering a mark is a teaching act; overseeing reports is an administrative one.

An administrator can no longer open or save the Report Entry grid for a
(class, subject) they do not teach — so a mark can never be authored against a
pupil in a teacher's stead. Everything administrative is deliberately untouched:
the broadsheet, the report card, the approve/publish ladder, and the School Head
comment, which is admin-ONLY and would break if "admins cannot write to reports"
had been applied bluntly.

Driven as the real roles. `manager` is the interesting one: it reaches mark entry
not through an explicit grant but through the `school:write` -> `school:reports:write`
scope hierarchy, which is why this had to be a code-level gate — no edit to the
permission presets could have removed it without stripping the whole school module.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup,
    GradingBand, GradingScale,
)
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import SCHOOL_PERMISSION_PRESETS, Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    _gate_comment_access, report_broadsheet, report_card, report_entry_grid,
    save_report_entry,
)
from app.schemas.platform import ReportEntrySave, ScoreItem
from tests._enrolment import enrol
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio


def _slot(class_id, subject_id, teacher_id, org_id, day=0):
    """A Timetable row. day_of_week / start_time / end_time are NOT NULL, so a
    bare (class, subject, teacher) triple will not insert."""
    return Timetable(id=str(uuid.uuid4()), class_id=class_id, subject_id=subject_id,
                     teacher_id=teacher_id, day_of_week=day, start_time="08:00",
                     end_time="09:00", org_id=org_id)


async def _user(db, org, slug, name):
    """A user holding the REAL preset for `slug`, not a hand-picked scope list."""
    r = Role(id=str(uuid.uuid4()), name=slug, slug=slug,
             permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id,
             is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _world(db, org):
    teacher = await _user(db, org, "teacher", "Real Teacher")
    admin = await _user(db, org, "manager", "An Administrator")

    sess = AcademicSession(id=str(uuid.uuid4()), name="2025/2026", term="Autumn",
                           is_current=True, org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                      teacher_id=teacher.id, org_id=org.id)
    _sec = await ensure_section(db, org)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    sc = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric",
                      is_provisional=False, purpose="grade", show_in_table=True, org_id=org.id)
    db.add_all([sess, term, full, cls, maths, pupil, grp, sc])
    await db.commit()
    db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade="C", remark="Good",
                       min_score=Decimal(0), max_score=Decimal(100), org_id=org.id))
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal("100"), session_id=sess.id, term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    # The Timetable is what assigns the teacher — the primary source
    # `_teacher_assignments` reads, and how all 120 live pairs are covered.
    db.add_all([asmt, _slot(cls.id, maths.id, teacher.id, org.id)])
    await db.commit()
    await enrol(db, org, pupil, maths)
    return dict(teacher=teacher, admin=admin, term=term, full=full, cls=cls,
                maths=maths, pupil=pupil, asmt=asmt)


def _payload(w):
    return ReportEntrySave(subject_id=w["maths"].id, class_id=w["cls"].id, items=[
        ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id, score=Decimal(70))])


# ── the restriction ──────────────────────────────────────────────────────────

async def test_an_admin_cannot_open_the_entry_grid(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await report_entry_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                term_id=w["term"].id, sub_term_id=w["full"].id,
                                db=db, current_user=w["admin"])
    assert e.value.status_code == 403


async def test_an_admin_cannot_save_a_mark(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=_payload(w), db=db, current_user=w["admin"])
    assert e.value.status_code == 403
    assert "do not teach this subject" in e.value.detail


async def test_the_admin_reached_it_via_the_scope_hierarchy_not_a_grant(db, org):
    """Why this had to be a code gate. `manager` holds no school:reports:write of
    its own — it inherits it from school:write, so removing the preset entry could
    not have closed this without stripping the entire school module."""
    w = await _world(db, org)
    perms = set(w["admin"].permissions)
    assert "school:reports:write" not in perms, "not granted explicitly"
    assert "school:write" in perms
    assert w["admin"].has_permission("school:reports:write"), "but inherited"
    assert w["admin"].has_permission("school_admin:read"), "and is a report admin"


async def test_the_assigned_teacher_still_can(db, org):
    """The other half: the restriction must not catch the person it exists for."""
    w = await _world(db, org)
    grid = await report_entry_grid(class_id=w["cls"].id, subject_id=w["maths"].id,
                                   term_id=w["term"].id, sub_term_id=w["full"].id,
                                   db=db, current_user=w["teacher"])
    assert [s.name for s in grid.students] == ["Ada Obi"]
    assert (await save_report_entry(payload=_payload(w), db=db,
                                    current_user=w["teacher"]))["saved"] == 1


async def test_an_admin_who_does_teach_it_can(db, org):
    """The rule is about the teaching relationship, not the job title. An
    administrator who genuinely teaches a class keeps entry for it."""
    w = await _world(db, org)
    db.add(_slot(w["cls"].id, w["maths"].id, w["admin"].id, org.id, day=1))
    await db.commit()

    assert (await save_report_entry(payload=_payload(w), db=db,
                                    current_user=w["admin"]))["saved"] == 1


async def test_class_id_is_now_required_of_everyone(db, org):
    """It was optional for admins only because their bypass left nothing to check
    it against."""
    w = await _world(db, org)
    payload = ReportEntrySave(subject_id=w["maths"].id, items=[
        ScoreItem(student_id=w["pupil"].id, assessment_id=w["asmt"].id, score=Decimal(70))])
    with pytest.raises(HTTPException) as e:
        await save_report_entry(payload=payload, db=db, current_user=w["admin"])
    assert e.value.status_code == 422
    assert "class_id is required" in e.value.detail


# ── oversight is UNTOUCHED — the load-bearing half ───────────────────────────

async def test_an_admin_still_sees_the_broadsheet(db, org):
    w = await _world(db, org)
    out = await report_broadsheet(class_id=w["cls"].id, term_id=w["term"].id,
                                  sub_term_id=w["full"].id, db=db, current_user=w["admin"])
    assert out.class_id == w["cls"].id


async def test_an_admin_still_opens_a_report_card(db, org):
    w = await _world(db, org)
    card = await report_card(student_id=w["pupil"].id, term_id=w["term"].id,
                             sub_term_id=w["full"].id, db=db, current_user=w["admin"])
    assert card.student_name == "Ada Obi"


async def test_the_school_head_comment_is_still_admin_only(db, org):
    """This would break under a blunt "admins cannot write to reports" reading:
    the head comment is admin-ONLY by design, and a teacher must not gain it."""
    w = await _world(db, org)
    await _gate_comment_access(db, org.id, w["admin"], w["cls"].id, "head")   # passes

    with pytest.raises(HTTPException) as e:
        await _gate_comment_access(db, org.id, w["teacher"], w["cls"].id, "head")
    assert e.value.status_code == 403


async def test_an_admin_can_still_submit_and_move_the_workflow(db, org):
    """The approve/publish ladder is administrative and stays so."""
    from app.routers.modules.academics import submit_class_report
    from app.schemas.academics import ReportSubmitRequest

    w = await _world(db, org)
    out = await submit_class_report(
        payload=ReportSubmitRequest(class_id=w["cls"].id, term_id=w["term"].id),
        db=db, current_user=w["admin"])
    assert out.stage == "submitted"
