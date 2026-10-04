"""Averages Across Terms and Academic Alert — two pivots of one load.

Both read `analyse_session_terms`, which runs `analyse_term` once per configured
(term, sub-term) of the session. Computed separately, a subject's term average
could disagree with the pupil movement printed beside it.

Production cannot exercise the cases that matter most. Its marks sit in a narrow
band — the steepest fall in the whole school is 7.6 points and nobody is below
the passmark — so `fell_below_pass` never fires there, and a conventional
10-point drop rule flags nobody at all. Those cases are built here, which is the
point: otherwise the first time anyone sees a below-passmark alert is the first
time it could be wrong.

What is pinned:

  AN UNMARKED TERM CONTRIBUTES NOTHING — not a zero. Its column still shows,
    because the layout is the school's reporting shape.
  THE THRESHOLD IS A PARAMETER, and the counts explain an empty result.
  EVERY REASON THAT APPLIES is carried, not just the first.
  A BELOW-PASSMARK CROSSING is caught even when the drop is small — the case a
    drop-size rule misses entirely.
  INCOMPLETE IS NOT FAILURE — a pupil missing a component has an unknown
    standing, and is flagged as a register gap rather than ranked low.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, AcademicTerm, Assessment, Cumulative,
    CumulativeComponent, ReportBranding, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import academic_alert, averages_across_terms
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


class W:
    pass


async def _world(db, org, *, passmark=40):
    w = W()
    w.sess = AcademicSession(id=str(uuid.uuid4()), name="2025/2026",
                             start_date=date(2025, 9, 15), end_date=date(2026, 7, 10),
                             is_current=True, org_id=org.id)
    w.autumn = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    w.spring = AcademicTerm(id=str(uuid.uuid4()), name="Spring", position=2, org_id=org.id)
    w.summer = AcademicTerm(id=str(uuid.uuid4()), name="Summer", position=3, org_id=org.id)
    w.full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=1, org_id=org.id)
    w.cls = SchoolClass(id=str(uuid.uuid4()), name="Year 10", level="YEAR 10", org_id=org.id)
    _sec = await ensure_section(db, org)
    w.maths = Subject(id=str(uuid.uuid4()), name="Mathematics", department="Mathematics",
                      section_id=_sec.id, org_id=org.id)
    w.eng = Subject(id=str(uuid.uuid4()), name="English", department="Languages",
                    section_id=_sec.id, org_id=org.id)
    db.add_all([w.sess, w.autumn, w.spring, w.summer, w.full, w.cls, w.maths, w.eng])
    db.add(ReportBranding(id=str(uuid.uuid4()), full_term_passmark=Decimal(passmark),
                          min_average_honours=Decimal(80), org_id=org.id))
    await db.commit()
    w.admin = await _admin(db, org)
    w.pupils = {}
    return w


async def _pupil(db, org, w, key, name):
    p = Student(id=str(uuid.uuid4()), student_id=f"FSN-{key}", first_name=name,
                last_name="Pupil", class_id=w.cls.id, org_id=org.id)
    db.add(p)
    await db.commit()
    w.pupils[key] = p
    return p


async def _configure(db, org, w, term, *, components=1):
    """An out-of-100 EXAM (+ optional CA) and a percentage TOTAL over them.

    With two components, a pupil marked on only one is PARTIALLY marked — which
    is what `incomplete` reports.
    """
    exam = Assessment(id=str(uuid.uuid4()), name="EXAM", max_score=Decimal("100"),
                      session_id=w.sess.id, term_id=term.id, sub_term_id=w.full.id,
                      org_id=org.id)
    db.add(exam)
    extra = None
    if components == 2:
        extra = Assessment(id=str(uuid.uuid4()), name="CA", max_score=Decimal("100"),
                           session_id=w.sess.id, term_id=term.id,
                           sub_term_id=w.full.id, org_id=org.id)
        db.add(extra)
    await db.commit()
    c = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                   session_id=w.sess.id, term_id=term.id, sub_term_id=w.full.id,
                   org_id=org.id)
    db.add(c)
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                               ref_type="assessment", ref_id=exam.id, position=0,
                               org_id=org.id))
    if extra is not None:
        db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=c.id,
                                   ref_type="assessment", ref_id=extra.id,
                                   position=1, org_id=org.id))
    await db.commit()
    return exam, extra


async def _mark(db, org, asmt, pupil, subject, score):
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=pupil.id, subject_id=subject.id,
        assessment_id=asmt.id, score=Decimal(score), source="entry", org_id=org.id))
    await db.commit()


# ── Averages Across Terms ────────────────────────────────────────────────────

async def test_subjects_are_averaged_per_term_with_a_trend(db, org):
    w = await _world(db, org)
    a = await _pupil(db, org, w, "0001", "Ada")
    b = await _pupil(db, org, w, "0002", "Bola")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    for p, s in ((a, 60), (b, 70)):
        await _mark(db, org, ex_a, p, w.maths, s)
    for p, s in ((a, 70), (b, 90)):
        await _mark(db, org, ex_s, p, w.maths, s)

    r = await averages_across_terms(sub_term_id=w.full.id, db=db, current_user=w.admin)
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[w.autumn.id].average == Decimal("65.00")
    assert row.cells[w.spring.id].average == Decimal("80.00")
    assert row.trend == Decimal("15.00")
    assert row.terms_counted == 2
    assert row.overall == Decimal("72.50")
    assert r.single_term is False and r.not_configured is False
    assert [c.term_name for c in r.columns] == ["Autumn", "Spring", "Summer"], (
        "columns in the school's term order, not an arbitrary one")


async def test_a_configured_but_unmarked_term_contributes_nothing(db, org):
    """Summer is set up and nobody has taught it. The subject average must stay
    at the marked terms' figure, not be dragged toward zero — and Summer's
    column must still appear."""
    w = await _world(db, org)
    a = await _pupil(db, org, w, "0001", "Ada")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    await _configure(db, org, w, w.summer)          # configured, unmarked
    await _mark(db, org, ex_a, a, w.maths, 60)

    r = await averages_across_terms(sub_term_id=w.full.id, db=db, current_user=w.admin)
    row = next(x for x in r.rows if x.subject_name == "Mathematics")
    assert row.cells[w.autumn.id].average == Decimal("60.00")
    assert w.summer.id not in row.cells, "no cell at all, rather than a zero"
    assert row.terms_counted == 1
    assert row.trend is None, "one marked term has no direction"
    assert r.single_term is True

    # `configured` means SET UP; `pupils_marked` means HAS DATA. They are
    # separate facts, and conflating them is what would turn "nobody has taught
    # Summer yet" into "Summer does not exist".
    summer_col = next(c for c in r.columns if c.term_name == "Summer")
    assert summer_col.configured is True, "Summer IS set up"
    assert summer_col.pupils_marked == 0, "it just has no marks"


async def test_nothing_configured_says_so(db, org):
    w = await _world(db, org)
    await _pupil(db, org, w, "0001", "Ada")
    r = await averages_across_terms(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert r.not_configured is True and r.rows == []


# ── Academic Alert ───────────────────────────────────────────────────────────

async def test_a_steep_drop_is_flagged_and_a_small_one_is_not(db, org):
    w = await _world(db, org)
    faller = await _pupil(db, org, w, "0001", "Faller")
    steady = await _pupil(db, org, w, "0002", "Steady")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, faller, w.maths, 80)
    await _mark(db, org, ex_s, faller, w.maths, 60)      # -20
    await _mark(db, org, ex_a, steady, w.maths, 70)
    await _mark(db, org, ex_s, steady, w.maths, 68)      # -2

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert r.considered == 2
    assert r.drop_threshold == Decimal("5.0"), "the documented default"
    names = [x.student_name for x in r.rows]
    assert "Faller Pupil" in names and "Steady Pupil" not in names
    row = next(x for x in r.rows if x.student_name == "Faller Pupil")
    assert row.reasons == ["steep_drop"]
    assert row.change == Decimal("-20.00")
    assert (row.first_term_name, row.last_term_name) == ("Autumn", "Spring")
    assert r.counts["steep_drop"] == 1


async def test_the_threshold_is_a_parameter(db, org):
    """The reason it is one: a threshold that suits one dataset flags nobody on
    another, and an empty report then looks broken rather than empty."""
    w = await _world(db, org)
    p = await _pupil(db, org, w, "0001", "Ada")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, p, w.maths, 70)
    await _mark(db, org, ex_s, p, w.maths, 63)          # -7

    lenient = await academic_alert(sub_term_id=w.full.id, drop_threshold=Decimal(5),
                                   db=db, current_user=w.admin)
    strict = await academic_alert(sub_term_id=w.full.id, drop_threshold=Decimal(10),
                                  db=db, current_user=w.admin)
    assert len(lenient.rows) == 1 and lenient.counts["steep_drop"] == 1
    assert len(strict.rows) == 0 and strict.counts["steep_drop"] == 0
    assert strict.considered == 1, (
        "an empty result must still say how many were considered, or it reads "
        "as 'not configured'")


async def test_falling_below_the_passmark_is_caught_even_when_the_drop_is_small(db, org):
    """The case a drop-size rule misses entirely: 42 -> 38 is a 4-point fall,
    under any sane steep-drop threshold, and it is the one that matters most.
    Production cannot show this — its passmark is 40 and nobody is near it."""
    w = await _world(db, org, passmark=40)
    p = await _pupil(db, org, w, "0001", "Edge")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, p, w.maths, 42)
    await _mark(db, org, ex_s, p, w.maths, 38)

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    row = next(x for x in r.rows if x.student_name == "Edge Pupil")
    assert "fell_below_pass" in row.reasons
    assert "steep_drop" not in row.reasons, "a 4-point fall is not steep"
    assert r.counts["fell_below_pass"] == 1
    assert r.passmark == Decimal("40.00")


async def test_a_pupil_carries_every_reason_that_applies(db, org):
    """Below the passmark AND a steep fall are two different conversations."""
    w = await _world(db, org, passmark=50)
    p = await _pupil(db, org, w, "0001", "Both")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, p, w.maths, 70)
    await _mark(db, org, ex_s, p, w.maths, 40)      # -30, and below 50

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    row = next(x for x in r.rows if x.student_name == "Both Pupil")
    assert set(row.reasons) == {"fell_below_pass", "steep_drop"}
    assert r.counts["fell_below_pass"] == 1 and r.counts["steep_drop"] == 1


async def test_an_incomplete_register_is_a_gap_not_a_failure(db, org):
    """A pupil marked on one of two components has an UNKNOWN standing in that
    subject, not a low one. Flagged as a register gap, with no movement figures
    invented for them."""
    w = await _world(db, org)
    p = await _pupil(db, org, w, "0001", "Partial")
    ex_a, ca_a = await _configure(db, org, w, w.autumn, components=2)
    await _mark(db, org, ex_a, p, w.maths, 60)     # EXAM only; CA missing

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    row = next(x for x in r.rows if x.student_name == "Partial Pupil")
    assert row.reasons == ["incomplete"]
    assert row.incomplete_subjects == ["Mathematics"]
    assert row.change is None, "no movement is invented for a partial register"
    assert r.counts["incomplete"] == 1


async def test_one_marked_term_reports_no_movement_but_still_flags_gaps(db, org):
    """With a single term there is nothing to compare, so no drop can be
    computed — but an incomplete register is still worth surfacing.

    The world needs a FULLY marked pupil for Autumn to count as marked at all: a
    term whose only pupil is partially marked produces no figures, so it is not
    a marked term and `single_term` would be False rather than True.
    """
    w = await _world(db, org)
    partial = await _pupil(db, org, w, "0001", "Partial")
    whole = await _pupil(db, org, w, "0002", "Whole")
    ex_a, ca_a = await _configure(db, org, w, w.autumn, components=2)
    await _mark(db, org, ex_a, partial, w.maths, 60)      # EXAM only
    await _mark(db, org, ex_a, whole, w.maths, 70)
    await _mark(db, org, ca_a, whole, w.maths, 70)        # both components

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert r.single_term is True, "Autumn is marked; Spring and Summer are not"
    assert r.not_configured is False
    assert r.considered == 0, "nobody has an average in TWO terms"
    assert r.counts["steep_drop"] == 0 and r.counts["fell_below_pass"] == 0
    assert r.counts["incomplete"] == 1
    assert [x.student_name for x in r.rows] == ["Partial Pupil"]


async def test_a_rise_is_never_flagged(db, org):
    w = await _world(db, org)
    p = await _pupil(db, org, w, "0001", "Riser")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, p, w.maths, 50)
    await _mark(db, org, ex_s, p, w.maths, 90)

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert r.rows == [] and r.considered == 1
    assert r.counts == {"fell_below_pass": 0, "steep_drop": 0, "incomplete": 0}


async def test_worst_fall_is_listed_first(db, org):
    w = await _world(db, org)
    small = await _pupil(db, org, w, "0001", "Small")
    big = await _pupil(db, org, w, "0002", "Big")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _mark(db, org, ex_a, small, w.maths, 70)
    await _mark(db, org, ex_s, small, w.maths, 63)      # -7
    await _mark(db, org, ex_a, big, w.maths, 90)
    await _mark(db, org, ex_s, big, w.maths, 50)        # -40

    r = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert [x.student_name for x in r.rows] == ["Big Pupil", "Small Pupil"]


# ── the two reports must agree ───────────────────────────────────────────────

async def test_both_reports_read_the_same_terms(db, org):
    """They share one load precisely so they cannot disagree about which terms
    are marked."""
    w = await _world(db, org)
    p = await _pupil(db, org, w, "0001", "Ada")
    ex_a, _ = await _configure(db, org, w, w.autumn)
    ex_s, _ = await _configure(db, org, w, w.spring)
    await _configure(db, org, w, w.summer)
    await _mark(db, org, ex_a, p, w.maths, 70)
    await _mark(db, org, ex_s, p, w.maths, 60)

    avg = await averages_across_terms(sub_term_id=w.full.id, db=db, current_user=w.admin)
    alert = await academic_alert(sub_term_id=w.full.id, db=db, current_user=w.admin)
    assert (alert.first_term_name, alert.last_term_name) == ("Autumn", "Spring")
    marked = [c.term_name for c in avg.columns if c.pupils_marked]
    assert marked == ["Autumn", "Spring"], "Summer is configured but unmarked"
    assert avg.single_term is False and alert.single_term is False
