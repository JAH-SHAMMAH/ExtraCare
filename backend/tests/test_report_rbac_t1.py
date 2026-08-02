"""Secondary Report T-1: role-based access — proves each block/allow as the REAL
consuming role (admin / class teacher / subject teacher / non-PC), not a synthetic
admin. Exercises the internal enforcement directly (class-teacher, Timetable
subject-scope, PC-teacher, admin bypass)."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import Subject, SchoolClass, Student, Timetable
from app.models.modules.platform import AcademicTerm, AcademicSubTerm, GradingScale, GradingBand, ClassPcTeacher
from app.routers.modules.platform import (
    bootstrap_assessments, bootstrap_cumulatives, list_assessments,
    report_entry_grid, save_report_entry, my_teaching_assignments,
    report_broadsheet, report_card, report_comment_grid, save_report_comments,
)
from app.schemas.platform import ReportEntrySave, ScoreItem, CommentGridSave, CommentItem


pytestmark = pytest.mark.asyncio


async def _user(db, org, name, perms):
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@x.com", full_name=name,
             status=UserStatus.ACTIVE, org_id=org.id)
    r = Role(id=str(uuid.uuid4()), name=name, slug=name, permissions=perms, org_id=org.id, is_system=False)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


TEACHER = ["school:read", "school:write"]      # holds school:reports:* via hierarchy, NOT school_admin
ADMIN = ["*"]


async def _fixture(db, org):
    admin = await _user(db, org, "admin", ADMIN)
    ct = await _user(db, org, "classteacher", TEACHER)      # the class/form teacher
    st = await _user(db, org, "subjectteacher", TEACHER)    # teaches Maths in the class (Timetable)
    other = await _user(db, org, "otherteacher", TEACHER)   # teaches nothing here

    autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="Year 11", level="YEAR 11", teacher_id=ct.id, org_id=org.id)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", org_id=org.id)
    stu = Student(id=str(uuid.uuid4()), student_id="FS/1", first_name="Ada", last_name="Obi", class_id=cls.id, org_id=org.id)
    tt = Timetable(id=str(uuid.uuid4()), class_id=cls.id, subject_id=maths.id, teacher_id=st.id,
                   day_of_week=0, start_time="08:00", end_time="09:00", org_id=org.id)
    scale = GradingScale(id=str(uuid.uuid4()), name="GRADING SCALE", scale_type="numeric", is_provisional=False,
                         purpose="grade", show_in_table=True, org_id=org.id)
    db.add_all([autumn, half, full, cls, maths, eng, stu, tt, scale])
    await db.flush()
    db.add(GradingBand(id=str(uuid.uuid4()), scale_id=scale.id, grade="A", min_score=Decimal(0), max_score=Decimal(100), org_id=org.id))
    await db.commit()
    await bootstrap_assessments(db=db, current_user=admin)
    await bootstrap_cumulatives(db=db, current_user=admin)
    A = {a.name: a for a in await list_assessments(term_id=autumn.id, db=db, current_user=admin)}
    return dict(admin=admin, ct=ct, st=st, other=other, autumn=autumn, half=half, full=full,
               cls=cls, maths=maths, eng=eng, stu=stu, A=A)


async def test_make_report_timetable_scope(db, org):
    f = await _fixture(db, org)
    entry = ReportEntrySave(subject_id=f["maths"].id, class_id=f["cls"].id,
                            items=[ScoreItem(student_id=f["stu"].id, assessment_id=f["A"]["EXAM"].id, score=Decimal("50"))])

    # Subject teacher teaches Maths in this class -> allowed.
    assert (await save_report_entry(payload=entry, db=db, current_user=f["st"]))["saved"] == 1
    grid = await report_entry_grid(class_id=f["cls"].id, subject_id=f["maths"].id, term_id=f["autumn"].id, db=db, current_user=f["st"])
    assert len(grid.students) == 1

    # Subject teacher does NOT teach English here -> blocked (grid + save).
    with pytest.raises(HTTPException) as ei:
        await report_entry_grid(class_id=f["cls"].id, subject_id=f["eng"].id, term_id=f["autumn"].id, db=db, current_user=f["st"])
    assert ei.value.status_code == 403
    with pytest.raises(HTTPException) as ei:
        await save_report_entry(payload=ReportEntrySave(subject_id=f["eng"].id, class_id=f["cls"].id,
                                items=[ScoreItem(student_id=f["stu"].id, assessment_id=f["A"]["EXAM"].id, score=Decimal("10"))]),
                                db=db, current_user=f["st"])
    assert ei.value.status_code == 403

    # Teacher who teaches nothing here -> blocked. Admin -> allowed.
    with pytest.raises(HTTPException) as ei:
        await report_entry_grid(class_id=f["cls"].id, subject_id=f["maths"].id, term_id=f["autumn"].id, db=db, current_user=f["other"])
    assert ei.value.status_code == 403
    assert (await report_entry_grid(class_id=f["cls"].id, subject_id=f["eng"].id, term_id=f["autumn"].id, db=db, current_user=f["admin"])) is not None

    # my-teaching-assignments reflects the Timetable.
    assigns = await my_teaching_assignments(db=db, current_user=f["st"])
    assert len(assigns) == 1 and assigns[0].class_id == f["cls"].id and assigns[0].subject_id == f["maths"].id
    assert await my_teaching_assignments(db=db, current_user=f["other"]) == []


async def test_reports_view_class_teacher_gate(db, org):
    f = await _fixture(db, org)
    await save_report_entry(payload=ReportEntrySave(subject_id=f["maths"].id, class_id=f["cls"].id,
                            items=[ScoreItem(student_id=f["stu"].id, assessment_id=f["A"]["EXAM"].id, score=Decimal("50"))]),
                            db=db, current_user=f["admin"])

    # Class teacher -> broadsheet + card allowed.
    assert (await report_broadsheet(class_id=f["cls"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id, db=db, current_user=f["ct"])) is not None
    assert (await report_card(student_id=f["stu"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id, db=db, current_user=f["ct"])) is not None

    # Subject teacher (NOT class teacher) -> blocked on both.
    for who in ("st", "other"):
        with pytest.raises(HTTPException) as ei:
            await report_broadsheet(class_id=f["cls"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id, db=db, current_user=f[who])
        assert ei.value.status_code == 403
        with pytest.raises(HTTPException) as ei:
            await report_card(student_id=f["stu"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id, db=db, current_user=f[who])
        assert ei.value.status_code == 403

    # Admin bypasses.
    assert (await report_broadsheet(class_id=f["cls"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id, db=db, current_user=f["admin"])) is not None


async def test_teacher_comments_pc_gate(db, org):
    f = await _fixture(db, org)
    args = dict(class_id=f["cls"].id, term_id=f["autumn"].id, sub_term_id=f["full"].id)

    # PC teacher defaults to the class teacher -> ct allowed on kind=pc.
    assert (await report_comment_grid(kind="pc", db=db, current_user=f["ct"], **args)) is not None
    save_pc = CommentGridSave(term_id=f["autumn"].id, sub_term_id=f["full"].id, kind="pc", class_id=f["cls"].id,
                              items=[CommentItem(student_id=f["stu"].id, text="Settled well.")])
    assert (await save_report_comments(payload=save_pc, db=db, current_user=f["ct"]))["saved"] == 1

    # Subject teacher (not PC) -> blocked on pc. Everyone non-admin -> blocked on head.
    with pytest.raises(HTTPException) as ei:
        await report_comment_grid(kind="pc", db=db, current_user=f["st"], **args)
    assert ei.value.status_code == 403
    with pytest.raises(HTTPException) as ei:
        await report_comment_grid(kind="head", db=db, current_user=f["ct"], **args)
    assert ei.value.status_code == 403
    # Admin can do head; PC teacher cannot.
    assert (await report_comment_grid(kind="head", db=db, current_user=f["admin"], **args)) is not None

    # Override the lookup: assign the SUBJECT teacher as PC -> now st allowed, ct blocked.
    db.add(ClassPcTeacher(id=str(uuid.uuid4()), class_id=f["cls"].id, teacher_id=f["st"].id, org_id=org.id))
    await db.commit()
    assert (await report_comment_grid(kind="pc", db=db, current_user=f["st"], **args)) is not None
    with pytest.raises(HTTPException) as ei:
        await report_comment_grid(kind="pc", db=db, current_user=f["ct"], **args)
    assert ei.value.status_code == 403
