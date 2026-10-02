"""StudentReport keyed by ids, not names (migration 135).

`student_reports` holds the only human-authored content on a report card that is
not a mark — the class-teacher and head-teacher comments, and the attendance
summary — and `report_card` used to find the row by comparing a term NAME. Rename
a term in Report Setup and the comparison matched nothing: every card silently
lost its comments and attendance, with no error. Fourth table with that defect,
after report_approvals (131), cbt_exams (132) and the report setup (134).

Four things are pinned:

  A RENAME NO LONGER STRANDS the row, which is the whole point.
  THE SESSION IS PART OF THE KEY — without it a pupil could hold exactly one
    report per term forever, and 2026/2027 Autumn would collide with
    2025/2026 Autumn. This is the case production cannot exercise yet.
  AN UNRESOLVABLE TERM IS REFUSED on write, rather than failing on a NOT NULL
    constraint nobody can read, and yields no row on read rather than a card
    with silently missing comments.
  THE DELETE GUARD counts these as HARD. They used to be counted as merely
    "stranded by name"; with ON DELETE CASCADE a confirmed term delete destroys
    them, and a warning that understates that is worse than the old silence.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import AcademicSession, AcademicTerm
from app.models.modules.school import SchoolClass, Student, StudentReport
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.school import get_report_card, upsert_report_meta
from app.schemas.grade import ReportMetaUpdate

pytestmark = pytest.mark.asyncio


async def _user(db, org, preset: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{preset}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


class W:
    pass


async def _world(db, org, *, second_session=False):
    w = W()
    w.autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    w.spring = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    w.old = AcademicSession(id=str(uuid.uuid4()), name="2025/2026",
                            start_date=date(2025, 9, 15), end_date=date(2026, 7, 10),
                            is_current=not second_session, org_id=org.id)
    db.add_all([w.autumn, w.spring, w.cls, w.old])
    if second_session:
        w.new = AcademicSession(id=str(uuid.uuid4()), name="2026/2027",
                                start_date=date(2026, 9, 15), end_date=date(2027, 7, 10),
                                is_current=True, org_id=org.id)
        db.add(w.new)
    await db.commit()
    w.pupil = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                      last_name="Obi", class_id=w.cls.id, org_id=org.id)
    db.add(w.pupil)
    await db.commit()
    w.admin = await _user(db, org, "org_admin")
    return w


# ── the rename that used to strand the row ───────────────────────────────────

async def test_renaming_a_term_no_longer_loses_the_comments(db, org):
    """The defect, directly. Author a report, rename the term, read the card by
    its NEW name: the comments must still be there.

    Before 135 the row stored 'Autumn' and the lookup compared against the new
    name, matched nothing, and the card came back with no comments and no
    attendance — silently."""
    w = await _world(db, org)
    await upsert_report_meta(
        student_id=w.pupil.id,
        payload=ReportMetaUpdate(class_teacher_comment="A thoughtful term.",
                                 attendance_present=50, attendance_total=60),
        term="Autumn", request=None, db=db, current_user=w.admin)
    await db.commit()

    w.autumn.name = "Michaelmas"
    await db.commit()

    row = (await db.execute(select(StudentReport).where(
        StudentReport.student_id == w.pupil.id))).scalar_one()
    assert row.term_id == w.autumn.id, "the row holds the ID, so the rename is a no-op"
    assert row.class_teacher_comment == "A thoughtful term."

    card = await get_report_card(student_id=w.pupil.id, term="Michaelmas",
                                 db=db, current_user=w.admin)
    # the card exposes these as teacher_remark / principal_remark
    assert card["teacher_remark"] == "A thoughtful term."
    assert card["attendance_present"] == 50 and card["attendance_total"] == 60


# ── the session is part of the key ───────────────────────────────────────────

async def test_the_same_term_in_two_sessions_holds_two_reports(db, org):
    """Without session_id in the key, a pupil could hold ONE report per term
    forever and this second write would collide with the first. Production
    cannot exercise this yet — only 2025/2026 has reports."""
    w = await _world(db, org, second_session=True)

    # 2026/2027 is current, so this files under it.
    await upsert_report_meta(
        student_id=w.pupil.id,
        payload=ReportMetaUpdate(class_teacher_comment="This year.",
                                 attendance_present=55, attendance_total=60),
        term="Autumn", request=None, db=db, current_user=w.admin)
    await db.commit()

    # Hand-file last year's Autumn report, which the old key could not express.
    db.add(StudentReport(id=str(uuid.uuid4()), student_id=w.pupil.id,
                         term_id=w.autumn.id, session_id=w.old.id,
                         class_teacher_comment="Last year.",
                         attendance_present=48, attendance_total=60,
                         org_id=org.id))
    await db.commit()

    rows = (await db.execute(select(StudentReport).where(
        StudentReport.student_id == w.pupil.id,
        StudentReport.term_id == w.autumn.id))).scalars().all()
    assert len(rows) == 2, "one Autumn report per SESSION, not per term"
    by_session = {r.session_id: r.class_teacher_comment for r in rows}
    assert by_session[w.new.id] == "This year."
    assert by_session[w.old.id] == "Last year."

    # And the card for the current session must not serve last year's.
    card = await get_report_card(student_id=w.pupil.id, term="Autumn",
                                 db=db, current_user=w.admin)
    assert card["teacher_remark"] == "This year."
    assert card["academic_year"] == "2026/2027", (
        "the displayed year comes from the session, now that academic_year is gone")


# ── an unresolvable term ─────────────────────────────────────────────────────

async def test_writing_an_unknown_term_is_refused_with_a_reason(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await upsert_report_meta(
            student_id=w.pupil.id,
            payload=ReportMetaUpdate(class_teacher_comment="x"),
            term="Trimester 7", request=None, db=db, current_user=w.admin)
    assert e.value.status_code == 422
    assert "not a term in your organisation" in str(e.value.detail)
    assert "Report Setup" in str(e.value.detail), "the refusal names its own fix"


async def test_reading_an_unknown_term_yields_no_comments_not_a_crash(db, org):
    """A read must degrade to "nothing authored", not 500 — the card still has
    marks to show."""
    w = await _world(db, org)
    card = await get_report_card(student_id=w.pupil.id, term="Trimester 7",
                                 db=db, current_user=w.admin)
    assert card["teacher_remark"] is None
    assert card["attendance_present"] is None


# ── the delete guard ─────────────────────────────────────────────────────────

async def test_the_term_delete_guard_counts_reports_as_destroyed(db, org):
    """They used to be counted as "stranded by name". With ON DELETE CASCADE a
    confirmed delete DESTROYS them, and these rows carry the only authored
    content on the card."""
    from app.routers.modules.platform import _term_delete_impact

    w = await _world(db, org)
    await upsert_report_meta(
        student_id=w.pupil.id,
        payload=ReportMetaUpdate(class_teacher_comment="Will be destroyed.",
                                 attendance_present=50, attendance_total=60),
        term="Autumn", request=None, db=db, current_user=w.admin)
    await db.commit()

    impact = await _term_delete_impact(db, org.id, w.autumn.id, "Autumn")
    hard = impact["hard"]
    assert hard.get("student reports (authored comments)") == 1, (
        f"must be counted as HARD, got hard={hard} soft={impact.get('soft')}")
    assert "student reports" not in (impact.get("soft") or {}), (
        "and must no longer be reported as merely stranded")
