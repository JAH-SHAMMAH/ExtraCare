"""Result Analysis Wave 1 — Remedial List + Honour Roll over one shared core.

The reports are thin readers of services/result_analysis.analyse_term. What is
worth testing is therefore less the arithmetic than the judgement calls, because
each one decides whether a real child appears on a list about them:

  * an UNMARKED pupil is on neither list — their average is unknown, not low;
  * "at or above" honours includes the pupil who scores the threshold exactly;
  * the pass mark is SUB-TERM aware, so mid_term_passmark is not dead config;
  * an unconfigured term says so, rather than reporting that nobody qualified.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, AssessmentGroup, Cumulative,
    CumulativeComponent, GradingBand, GradingScale, ReportBranding,
    StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role
from app.models.user import User, UserStatus
from app.routers.modules.platform import honour_roll, remedial_list
from tests.conftest import ensure_session
from tests.conftest import ensure_section

pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    r = Role(id=str(uuid.uuid4()), name="admin", slug="super_user",
             permissions=["*"], org_id=org.id, is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com",
             full_name="Officer", status=UserStatus.ACTIVE, org_id=org.id)
    db.add(r)
    u.roles = [r]
    db.add(u)
    await db.commit()
    return u


async def _world(db, org, *, passmark=40, honours=80, mid_passmark=35):
    """One class, two subjects, Fairview's nine bands, a TOTAL(percentage) over a
    single /100 assessment — so a raw mark IS the percentage and the arithmetic
    under test stays visible."""
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    half = AcademicSubTerm(id=str(uuid.uuid4()), name="Half-Term", position=1, org_id=org.id)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1", org_id=org.id)
    _sec = await ensure_section(db, org)
    maths = Subject(id=str(uuid.uuid4()), name="Mathematics", section_id=_sec.id, org_id=org.id)
    eng = Subject(id=str(uuid.uuid4()), name="English", section_id=_sec.id, org_id=org.id)
    grp = AssessmentGroup(id=str(uuid.uuid4()), name="CBT", position=0, org_id=org.id)
    sc = GradingScale(id=str(uuid.uuid4()), name="Nigerian Secondary (A*-F)",
                      scale_type="numeric", purpose="grade", show_in_table=True,
                      is_provisional=True, org_id=org.id)
    db.add_all([term, full, half, cls, maths, eng, grp, sc,
                ReportBranding(id=str(uuid.uuid4()), org_id=org.id,
                               full_term_passmark=Decimal(passmark),
                               mid_term_passmark=Decimal(mid_passmark),
                               min_average_honours=Decimal(honours))])
    await db.commit()
    for i, (g, lo, hi) in enumerate([
        ("A*", 95, 100), ("A", 90, 94), ("B+", 85, 89), ("B", 80, 84), ("C", 70, 79),
        ("D", 60, 69), ("E", 50, 59), ("P", 40, 49), ("F", 0, 39),
    ]):
        db.add(GradingBand(id=str(uuid.uuid4()), scale_id=sc.id, grade=g,
                           min_score=Decimal(lo), max_score=Decimal(hi),
                           position=i, org_id=org.id))
    _sess = await ensure_session(db, org)
    asmt = Assessment(id=str(uuid.uuid4()), name="CBT Exam Score", code="CBT",
                      max_score=Decimal(100), session_id=_sess.id, term_id=term.id, sub_term_id=full.id,
                      group_id=grp.id, decimal_places=0, position=0, org_id=org.id)
    db.add(asmt)
    await db.commit()
    for sub_term in (full, half):
        _sess = await ensure_session(db, org)
        cum = Cumulative(id=str(uuid.uuid4()), name="TOTAL", session_id=_sess.id, term_id=term.id,
                         sub_term_id=sub_term.id, cumul_type="percentage",
                         decimal_places=2, position=0, org_id=org.id)
        db.add(cum)
        await db.flush()
        db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=cum.id,
                                   ref_type="assessment", ref_id=asmt.id,
                                   position=0, org_id=org.id))
    await db.commit()
    return dict(term=term, full=full, half=half, cls=cls, maths=maths, eng=eng, asmt=asmt)


async def _pupil(db, org, w, name, marks):
    """marks = {subject: pct}. An empty dict means an unmarked pupil."""
    first, last = name.split()
    st = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:4]}",
                 first_name=first, last_name=last, class_id=w["cls"].id, org_id=org.id)
    db.add(st)
    await db.commit()
    for subj, pct in marks.items():
        db.add(StudentAssessmentScore(
            id=str(uuid.uuid4()), student_id=st.id, subject_id=subj.id,
            assessment_id=w["asmt"].id, score=Decimal(pct), source="entry", org_id=org.id))
    await db.commit()
    return st


def _args(w, sub_term=None):
    return dict(term_id=w["term"].id, sub_term_id=(sub_term or w["full"]).id)


# ── Remedial List ────────────────────────────────────────────────────────────

async def test_lists_only_pupils_below_the_passmark(db, org):
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Low Scorer", {w["maths"]: 30, w["eng"]: 20})    # avg 25
    await _pupil(db, org, w, "Fine Scorer", {w["maths"]: 70, w["eng"]: 60})   # avg 65

    out = await remedial_list(**_args(w), db=db, current_user=admin)

    assert out.threshold == Decimal("40") and out.threshold_source == "configured"
    assert [p.student_name for p in out.pupils] == ["Low Scorer"]
    assert out.pupils[0].average == Decimal("25.00")
    assert out.considered == 2 and out.unmarked == 0


async def test_an_unmarked_pupil_is_never_called_failing(db, org):
    """THE one that matters. An unknown average is not a low one, and printing a
    child as needing remediation because nobody entered their marks would be a real
    error about a real child."""
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "No Marks", {})
    await _pupil(db, org, w, "Low Scorer", {w["maths"]: 10})

    out = await remedial_list(**_args(w), db=db, current_user=admin)

    assert [p.student_name for p in out.pupils] == ["Low Scorer"]
    assert out.unmarked == 1, "counted, not listed, and not silently dropped"
    assert out.considered == 1


async def test_it_says_which_subjects_to_remediate(db, org):
    """A list of names says who is struggling; names with subjects say what to do."""
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Mixed Scorer", {w["maths"]: 15, w["eng"]: 45})   # avg 30

    out = await remedial_list(**_args(w), db=db, current_user=admin)

    p = out.pupils[0]
    assert p.average == Decimal("30.00")
    names = [x.subject_name for x in p.subjects_below]
    assert names == ["Mathematics"], "English at 45 is above the passmark"
    assert p.subjects_below[0].percentage == Decimal("15.00")


async def test_worst_first(db, org):
    """A remedial list is a work queue."""
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Bad One", {w["maths"]: 35})
    await _pupil(db, org, w, "Worse One", {w["maths"]: 5})

    out = await remedial_list(**_args(w), db=db, current_user=admin)
    assert [p.student_name for p in out.pupils] == ["Worse One", "Bad One"]


async def test_the_passmark_is_sub_term_aware(db, org):
    """ReportBranding carries BOTH full and mid term pass marks; using one for both
    would make half that configuration dead."""
    admin = await _admin(db, org)
    w = await _world(db, org, passmark=40, mid_passmark=35)
    await _pupil(db, org, w, "Between Marks", {w["maths"]: 37})

    full_out = await remedial_list(**_args(w), db=db, current_user=admin)
    assert full_out.threshold == Decimal("40")
    assert [p.student_name for p in full_out.pupils] == ["Between Marks"]

    half_out = await remedial_list(**_args(w, w["half"]), db=db, current_user=admin)
    assert half_out.threshold == Decimal("35"), "the Half-Term mark applies"
    assert half_out.pupils == [], "37 clears the mid-term bar"


# ── Honour Roll ──────────────────────────────────────────────────────────────

async def test_honour_roll_is_best_first_with_positions(db, org):
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Very Good", {w["maths"]: 90, w["eng"]: 92})   # 91
    await _pupil(db, org, w, "Excellent One", {w["maths"]: 99, w["eng"]: 97})  # 98
    await _pupil(db, org, w, "Ordinary One", {w["maths"]: 55})

    out = await honour_roll(**_args(w), db=db, current_user=admin)

    assert out.threshold == Decimal("80")
    assert [p.student_name for p in out.pupils] == ["Excellent One", "Very Good"]
    assert [p.position for p in out.pupils] == [1, 2]
    assert out.pupils[0].grade == "A*"


async def test_exactly_the_threshold_qualifies(db, org):
    """AT or above. Excluding an exact match would make the configured number mean
    something a hundredth away from what it says."""
    admin = await _admin(db, org)
    w = await _world(db, org, honours=80)
    await _pupil(db, org, w, "Exactly Eighty", {w["maths"]: 80})
    await _pupil(db, org, w, "Just Under", {w["maths"]: 79})

    out = await honour_roll(**_args(w), db=db, current_user=admin)
    assert [p.student_name for p in out.pupils] == ["Exactly Eighty"]


async def test_unmarked_pupils_are_not_honoured_either(db, org):
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "No Marks", {})
    out = await honour_roll(**_args(w), db=db, current_user=admin)
    assert out.pupils == [] and out.unmarked == 1


# ── the shared core's own contract ───────────────────────────────────────────

async def test_an_unconfigured_term_says_so_rather_than_nobody_qualified(db, org):
    """The empty-cumulative condition that made every subject grade F. An empty list
    with not_configured=False would read as a settled fact about the pupils."""
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Some Pupil", {w["maths"]: 70})
    # Remove the cumulatives, leaving the marks in place.
    from sqlalchemy import delete
    await db.execute(delete(CumulativeComponent))
    await db.execute(delete(Cumulative))
    await db.commit()

    out = await remedial_list(**_args(w), db=db, current_user=admin)
    assert out.not_configured is True
    assert out.pupils == [] and out.considered == 0


async def test_class_scope_narrows_the_school(db, org):
    admin = await _admin(db, org)
    w = await _world(db, org)
    other = SchoolClass(id=str(uuid.uuid4()), name="JSS1 B", level="JSS1", org_id=org.id)
    db.add(other)
    await db.commit()
    await _pupil(db, org, w, "In Scope", {w["maths"]: 10})
    outsider = Student(id=str(uuid.uuid4()), student_id="S-OUT", first_name="Out",
                       last_name="Scope", class_id=other.id, org_id=org.id)
    db.add(outsider)
    await db.commit()
    db.add(StudentAssessmentScore(id=str(uuid.uuid4()), student_id=outsider.id,
                                  subject_id=w["maths"].id, assessment_id=w["asmt"].id,
                                  score=Decimal(5), source="entry", org_id=org.id))
    await db.commit()

    scoped = await remedial_list(**_args(w), class_id=w["cls"].id, db=db, current_user=admin)
    assert [p.student_name for p in scoped.pupils] == ["In Scope"]
    assert scoped.class_name == "JSS1 A"

    school = await remedial_list(**_args(w), db=db, current_user=admin)
    assert len(school.pupils) == 2, "unscoped covers both classes"


async def test_both_reports_agree_on_the_same_pupil(db, org):
    """The reason for a shared core: two independent loops would eventually
    disagree about one pupil's average."""
    admin = await _admin(db, org)
    w = await _world(db, org)
    await _pupil(db, org, w, "Middle Pupil", {w["maths"]: 60, w["eng"]: 80})   # 70

    rem = await remedial_list(**_args(w), db=db, current_user=admin)
    hon = await honour_roll(**_args(w), db=db, current_user=admin)
    assert rem.pupils == [] and hon.pupils == [], "70 is neither failing nor honoured"
    assert rem.considered == hon.considered == 1
