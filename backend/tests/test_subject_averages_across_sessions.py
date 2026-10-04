"""Subjects Averages Across Sessions — the report migration 134 existed for.

Terms are shared across sessions, so before `assessments.session_id` there was no
way to tell 2025/2026's Autumn from 2026/2027's and any cross-year figure would
silently have been a blend. These prove it is not.

Production cannot exercise the interesting case yet: only 2025/2026 holds marks,
so there is nothing to compare it against and no trend to compute. The two-year
grid is built here instead, which is the whole reason to have the tests —
otherwise the first time anyone sees a trend is the first time it could be wrong.

Four things are pinned:

  SEPARATION — the same subject in the same term, in two sessions, yields two
    different figures and neither leaks into the other.
  TERM FOLDING — a session's figure is the unweighted mean of its terms, and an
    unmarked term contributes NOTHING rather than a zero.
  HONEST GAPS — a session with no setup renders not_configured, never 0; one
    session alone reports single_session rather than a trend.
  LIKE WITH LIKE — the sub-term is a parameter, so a Mock does not average into
    a Full-Term.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, Cumulative,
    CumulativeComponent, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import subject_averages_across_sessions
from tests.conftest import ensure_section

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


class World:
    pass


async def _base(db, org):
    """Terms, sub-terms, a class, two subjects, two pupils. Shared across years —
    which is exactly the thing that made this report impossible before 134."""
    w = World()
    w.autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    w.spring = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    w.full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    w.mock = AcademicSubTerm(id=str(uuid.uuid4()), name="Mock", position=2, org_id=org.id)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    _sec = await ensure_section(db, org)
    w.maths = Subject(id=str(uuid.uuid4()), name="Mathematics", department="Sciences",
                      section_id=_sec.id, org_id=org.id)
    w.eng = Subject(id=str(uuid.uuid4()), name="English", department="Languages",
                    section_id=_sec.id, org_id=org.id)
    db.add_all([w.autumn, w.spring, w.full, w.mock, w.cls, w.maths, w.eng])
    await db.commit()
    w.a = Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                  last_name="Obi", class_id=w.cls.id, org_id=org.id)
    w.b = Student(id=str(uuid.uuid4()), student_id="FSN-0002", first_name="Bola",
                  last_name="Eze", class_id=w.cls.id, org_id=org.id)
    db.add_all([w.a, w.b])
    await db.commit()
    return w


async def _year(db, org, name, *, current=False, start_year=2025):
    s = AcademicSession(id=str(uuid.uuid4()), name=name, term=None,
                        start_date=date(start_year, 9, 15),
                        end_date=date(start_year + 1, 7, 10),
                        is_current=current, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _configure(db, org, sess, term, sub):
    """One out-of-100 assessment and a percentage TOTAL over it."""
    a = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=Decimal("100"),
                   session_id=sess.id, term_id=term.id, sub_term_id=sub.id,
                   org_id=org.id)
    db.add(a)
    await db.commit()
    c = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                   session_id=sess.id, term_id=term.id, sub_term_id=sub.id,
                   org_id=org.id)
    db.add(c)
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                               ref_type="assessment", ref_id=a.id, position=0,
                               org_id=org.id))
    await db.commit()
    return a


async def _mark(db, org, asmt, pupil, subject, score):
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=pupil.id, subject_id=subject.id,
        assessment_id=asmt.id, score=Decimal(score), source="entry", org_id=org.id))
    await db.commit()


# ── separation ───────────────────────────────────────────────────────────────

async def test_the_same_term_in_two_sessions_gives_two_figures(db, org):
    """Maths averages 40 in 2025/2026 Autumn and 80 in 2026/2027 Autumn. ONE
    `academic_terms` row backs both. A blend would read 60 — plausible, and
    wrong."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    old = await _year(db, org, "2025/2026", start_year=2025)
    new = await _year(db, org, "2026/2027", current=True, start_year=2026)

    a_old = await _configure(db, org, old, w.autumn, w.full)
    await _mark(db, org, a_old, w.a, w.maths, 40)
    await _mark(db, org, a_old, w.b, w.maths, 40)

    a_new = await _configure(db, org, new, w.autumn, w.full)
    await _mark(db, org, a_new, w.a, w.maths, 80)
    await _mark(db, org, a_new, w.b, w.maths, 80)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)

    assert [c.session_name for c in r.columns] == ["2025/2026", "2026/2027"], (
        "columns must read chronologically, so a trend has a direction")
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[old.id].average == Decimal("40.00")
    assert row.cells[new.id].average == Decimal("80.00")
    assert row.trend == Decimal("40.00"), "latest minus earliest"
    assert row.sessions_counted == 2
    assert r.single_session is False


async def test_a_pupils_other_year_does_not_reach_this_one(db, org):
    """Only one year is set up. The other year's marks exist but must not appear
    anywhere in the figure for the year that is."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    old = await _year(db, org, "2025/2026", current=True, start_year=2025)
    new = await _year(db, org, "2026/2027", start_year=2026)

    a_old = await _configure(db, org, old, w.autumn, w.full)
    await _mark(db, org, a_old, w.a, w.maths, 50)
    a_new = await _configure(db, org, new, w.autumn, w.full)
    await _mark(db, org, a_new, w.a, w.maths, 100)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[old.id].average == Decimal("50.00")
    assert row.cells[new.id].average == Decimal("100.00")
    assert row.overall == Decimal("75.00"), "mean of the years it HAS"


# ── term folding ─────────────────────────────────────────────────────────────

async def test_a_session_average_is_the_mean_of_its_terms(db, org):
    """Autumn 40, Spring 60 -> the year is 50, and says it rests on two terms."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    yr = await _year(db, org, "2025/2026", current=True)

    a1 = await _configure(db, org, yr, w.autumn, w.full)
    await _mark(db, org, a1, w.a, w.maths, 40)
    a2 = await _configure(db, org, yr, w.spring, w.full)
    await _mark(db, org, a2, w.a, w.maths, 60)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[yr.id].average == Decimal("50.00")
    assert row.cells[yr.id].terms_counted == 2
    assert row.cells[yr.id].entered == 2
    col = r.columns[0]
    assert col.terms_counted == 2 and sorted(col.term_names) == ["Autumn", "Spring"]


async def test_an_unmarked_term_is_not_counted_as_zero(db, org):
    """Spring is configured and nobody has taught it yet. The year must stay 40,
    not fall to 20 — the exact shape of the bug that graded a whole school F."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    yr = await _year(db, org, "2025/2026", current=True)

    a1 = await _configure(db, org, yr, w.autumn, w.full)
    await _mark(db, org, a1, w.a, w.maths, 40)
    await _configure(db, org, yr, w.spring, w.full)      # configured, unmarked

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[yr.id].average == Decimal("40.00"), (
        "an unmarked term must contribute nothing, not a zero")
    assert row.cells[yr.id].terms_counted == 1, "and must say so"
    assert r.columns[0].terms_counted == 1


# ── honest gaps ──────────────────────────────────────────────────────────────

async def test_an_empty_year_is_a_column_that_says_so(db, org):
    """2026/2027 exists with no setup — exactly production's state. It appears as
    a column marked not_configured, with no cell, rather than being dropped from
    the grid or shown as 0."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    old = await _year(db, org, "2025/2026", current=True, start_year=2025)
    new = await _year(db, org, "2026/2027", start_year=2026)

    a = await _configure(db, org, old, w.autumn, w.full)
    await _mark(db, org, a, w.a, w.maths, 70)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)

    cols = {c.session_name: c for c in r.columns}
    assert cols["2026/2027"].not_configured is True
    assert cols["2026/2027"].terms_counted == 0
    assert cols["2025/2026"].not_configured is False

    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert new.id not in row.cells, "no cell at all, rather than a zero"
    assert row.trend is None, "one year has no direction"
    assert r.single_session is True, "and the page should be able to explain that"
    assert r.not_configured is False, "something WAS computable"


async def test_nothing_set_up_anywhere_says_not_configured(db, org):
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    await _year(db, org, "2025/2026", current=True)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    assert r.not_configured is True
    assert r.rows == []


# ── like with like ───────────────────────────────────────────────────────────

async def test_a_mock_does_not_average_into_a_full_term(db, org):
    """The sub-term is a parameter precisely so these stay apart. Asking for Mock
    must return the Mock figure, not a blend with the Full-Term."""
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    yr = await _year(db, org, "2025/2026", current=True)

    a_full = await _configure(db, org, yr, w.autumn, w.full)
    await _mark(db, org, a_full, w.a, w.maths, 90)
    a_mock = await _configure(db, org, yr, w.autumn, w.mock)
    await _mark(db, org, a_mock, w.a, w.maths, 30)

    full = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    mock = await subject_averages_across_sessions(
        sub_term_id=w.mock.id, db=db, current_user=admin)

    assert next(x for x in full.rows if x.subject_name == "Mathematics") \
        .cells[yr.id].average == Decimal("90.00")
    assert next(x for x in mock.rows if x.subject_name == "Mathematics") \
        .cells[yr.id].average == Decimal("30.00")
    assert full.sub_term_name == "Full-Term" and mock.sub_term_name == "Mock"


# ── scoping ──────────────────────────────────────────────────────────────────

async def test_a_teacher_cannot_open_the_whole_school(db, org):
    """Same rule as the other admin pivots, enforced on the server rather than by
    hiding the tab."""
    w = await _base(db, org)
    teacher = await _user(db, org, "teacher")
    await _year(db, org, "2025/2026", current=True)

    with pytest.raises(HTTPException) as e:
        await subject_averages_across_sessions(
            sub_term_id=w.full.id, db=db, current_user=teacher)
    assert e.value.status_code == 403
    assert "administrators only" in str(e.value.detail)


async def test_the_department_comes_through_for_grouping(db, org):
    w = await _base(db, org)
    admin = await _user(db, org, "org_admin")
    yr = await _year(db, org, "2025/2026", current=True)
    a = await _configure(db, org, yr, w.autumn, w.full)
    await _mark(db, org, a, w.a, w.maths, 55)
    await _mark(db, org, a, w.a, w.eng, 65)

    r = await subject_averages_across_sessions(
        sub_term_id=w.full.id, db=db, current_user=admin)
    depts = {x.subject_name: x.department for x in r.rows}
    assert depts == {"Mathematics": "Sciences", "English": "Languages"}
    assert [x.subject_name for x in r.rows] == ["English", "Mathematics"], (
        "alphabetical, so the grid is scannable")
