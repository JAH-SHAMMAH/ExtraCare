"""Order of Merit, Grade Summary Sheet, Subject Performance Analysis.

These are PIVOTS of `analyse_term`, so the arithmetic is not retested here — it is
pinned once, where it lives. What is pinned here is what a pivot can get wrong:

  * ranking:      ties, and never ranking an unmarked pupil;
  * banding:      the school's own bands, in its own order, not a hardcoded A-F;
  * aggregation:  a partially-marked pupil excluded from every figure rather than
                  folded in at a deflated value;
  * the three states that must stay distinct — marked, unmarked, not configured.

The last one is why these exist: an empty report that means "nobody qualified"
and one that means "the term was never set up" look identical on a page, and only
one of them is a reason to worry.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
    GradingBand, GradingScale, StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import (
    grade_summary, order_of_merit, subject_performance,
)


async def _admin(db, org) -> User:
    role = Role(id=str(uuid.uuid4()), name="org_admin", slug=f"a-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS["org_admin"]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@example.com",
             full_name="Admin", status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _bands(db, org):
    scale = GradingScale(id=str(uuid.uuid4()), name="A-F", scale_type="numeric",
                         purpose="grade", show_in_table=True, org_id=org.id)
    db.add(scale)
    await db.commit()
    for grade, lo in [("A", 70), ("B", 60), ("C", 50), ("F", 0)]:
        db.add(GradingBand(id=str(uuid.uuid4()), grade=grade, min_score=lo,
                           max_score=100, scale_id=scale.id, org_id=org.id))
    await db.commit()


async def _world(db, org, *, marks: dict[str, dict[str, int]], weighted: bool = False):
    """marks = {pupil_name: {subject_name: exam_score}}.

    `weighted` adds an unmarked CA component so a subject can be made INCOMPLETE —
    the case where a pupil has marks but not all of them.
    """
    await _bands(db, org)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", position=2, org_id=org.id)
    db.add_all([cls, term, full])
    await db.commit()

    subject_names = sorted({s for m in marks.values() for s in m})
    subjects = {}
    for name in subject_names:
        s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
        subjects[name] = s
        db.add(s)
    pupils = {}
    for name in marks:
        first, last = name.split(" ", 1)
        p = Student(id=str(uuid.uuid4()), student_id=f"S-{uuid.uuid4().hex[:4]}",
                    first_name=first, last_name=last, class_id=cls.id, org_id=org.id)
        pupils[name] = p
        db.add(p)
    await db.commit()

    exam = Assessment(id=str(uuid.uuid4()), name="Exam", max_score=100,
                      term_id=term.id, sub_term_id=full.id, org_id=org.id)
    db.add(exam)
    await db.commit()
    total = Cumulative(id=str(uuid.uuid4()), name="TOTAL", cumul_type="percentage",
                       term_id=term.id, sub_term_id=full.id, org_id=org.id)
    db.add(total)
    await db.commit()
    db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=total.id,
                               ref_type="assessment", ref_id=exam.id, position=0,
                               org_id=org.id))
    ca = None
    if weighted:
        ca = Assessment(id=str(uuid.uuid4()), name="CA", max_score=40,
                        term_id=term.id, sub_term_id=full.id, org_id=org.id)
        db.add(ca)
        await db.commit()
        db.add(CumulativeComponent(id=str(uuid.uuid4()), cumulative_id=total.id,
                                   ref_type="assessment", ref_id=ca.id, position=1,
                                   org_id=org.id))
    await db.commit()

    for pname, subs in marks.items():
        for sname, score in subs.items():
            db.add(StudentAssessmentScore(
                id=str(uuid.uuid4()), student_id=pupils[pname].id,
                subject_id=subjects[sname].id, assessment_id=exam.id,
                score=score, org_id=org.id))
    await db.commit()
    return dict(cls=cls, term=term, full=full, subjects=subjects, pupils=pupils,
                exam=exam, ca=ca)


# ── Order of Merit ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_merit_ranks_best_first(db, org):
    w = await _world(db, org, marks={
        "Ada Obi": {"Maths": 90}, "Bode Ade": {"Maths": 70}, "Chi Eze": {"Maths": 50}})
    admin = await _admin(db, org)
    res = await order_of_merit(term_id=w["term"].id, sub_term_id=w["full"].id,
                               class_id=w["cls"].id, db=db, current_user=admin)
    assert [r.student_name for r in res.rows] == ["Ada Obi", "Bode Ade", "Chi Eze"]
    assert [r.position for r in res.rows] == [1, 2, 3]
    assert res.considered == 3 and res.unmarked == 0


@pytest.mark.asyncio
async def test_merit_uses_standard_competition_ranking(db, org):
    """1, 2, 2, 4 — two equal averages are the same position, and the next pupil
    takes the place their count implies. Dense ranking (1, 2, 2, 3) would assert
    an order the marks do not contain. Educare's convention is unverified."""
    w = await _world(db, org, marks={
        "Ada Obi": {"Maths": 90}, "Bode Ade": {"Maths": 70},
        "Chi Eze": {"Maths": 70}, "Dayo Ola": {"Maths": 50}})
    admin = await _admin(db, org)
    res = await order_of_merit(term_id=w["term"].id, sub_term_id=w["full"].id,
                               class_id=w["cls"].id, db=db, current_user=admin)
    assert [r.position for r in res.rows] == [1, 2, 2, 4]
    tied = {r.student_name for r in res.rows if r.tied}
    assert tied == {"Bode Ade", "Chi Eze"}


@pytest.mark.asyncio
async def test_merit_never_ranks_an_unmarked_pupil(db, org):
    """Their standing is unknown, not last. A merit list that placed them would be
    inventing a result for a child."""
    w = await _world(db, org, marks={"Ada Obi": {"Maths": 90}})
    extra = Student(id=str(uuid.uuid4()), student_id="S-none", first_name="Unmarked",
                    last_name="Pupil", class_id=w["cls"].id, org_id=org.id)
    db.add(extra)
    await db.commit()
    admin = await _admin(db, org)
    res = await order_of_merit(term_id=w["term"].id, sub_term_id=w["full"].id,
                               class_id=w["cls"].id, db=db, current_user=admin)
    assert [r.student_name for r in res.rows] == ["Ada Obi"]
    assert res.unmarked == 1


# ── Grade Summary ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_grade_summary_uses_the_schools_own_bands(db, org):
    """Columns are whatever the school configured, in its own order — not a
    hardcoded A-F that would quietly mis-file a renamed band."""
    w = await _world(db, org, marks={
        "Ada Obi": {"Maths": 90, "English": 65},
        "Bode Ade": {"Maths": 55, "English": 20}})
    admin = await _admin(db, org)
    res = await grade_summary(term_id=w["term"].id, sub_term_id=w["full"].id,
                              class_id=w["cls"].id, db=db, current_user=admin)
    assert res.grades == ["A", "B", "C", "F"], "best first, from the configured scale"
    maths = next(r for r in res.rows if r.subject_name == "Maths")
    assert maths.counts == {"A": 1, "B": 0, "C": 1, "F": 0}
    assert maths.entered == 2
    english = next(r for r in res.rows if r.subject_name == "English")
    assert english.counts == {"A": 0, "B": 1, "C": 0, "F": 1}


@pytest.mark.asyncio
async def test_grade_summary_totals_every_subject(db, org):
    w = await _world(db, org, marks={
        "Ada Obi": {"Maths": 90, "English": 65},
        "Bode Ade": {"Maths": 55, "English": 20}})
    admin = await _admin(db, org)
    res = await grade_summary(term_id=w["term"].id, sub_term_id=w["full"].id,
                              class_id=w["cls"].id, db=db, current_user=admin)
    assert res.total_row.subject_name == "All subjects"
    assert res.total_row.entered == 4
    assert res.total_row.counts == {"A": 1, "B": 1, "C": 1, "F": 1}


# ── Subject Performance ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_subject_performance_reports_range_and_pass_rate(db, org):
    w = await _world(db, org, marks={
        "Ada Obi": {"Maths": 90}, "Bode Ade": {"Maths": 60}, "Chi Eze": {"Maths": 30}})
    admin = await _admin(db, org)
    res = await subject_performance(term_id=w["term"].id, sub_term_id=w["full"].id,
                                    class_id=w["cls"].id, db=db, current_user=admin)
    row = next(r for r in res.rows if r.subject_name == "Maths")
    assert row.entered == 3
    assert float(row.highest) == 90 and float(row.lowest) == 30
    assert float(row.average) == 60
    # default passmark is 40 -> two of three pass
    assert row.passed == 2 and row.failed == 1
    assert float(row.pass_rate) == pytest.approx(66.7, abs=0.1)
    assert res.threshold_source in ("configured", "partial", "default")


@pytest.mark.asyncio
async def test_subject_performance_excludes_a_partially_marked_pupil(db, org):
    """A pupil with an exam mark and no CA is counted as incomplete, not as a low
    score: folding them in would understate the subject's mean and fail a child
    for a mark their teacher has not entered."""
    w = await _world(db, org, weighted=True,
                     marks={"Ada Obi": {"Maths": 90}, "Bode Ade": {"Maths": 60}})
    # Ada has a CA mark; Bode does not.
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=w["pupils"]["Ada Obi"].id,
        subject_id=w["subjects"]["Maths"].id, assessment_id=w["ca"].id,
        score=40, org_id=org.id))
    await db.commit()
    admin = await _admin(db, org)

    res = await subject_performance(term_id=w["term"].id, sub_term_id=w["full"].id,
                                    class_id=w["cls"].id, db=db, current_user=admin)
    row = next(r for r in res.rows if r.subject_name == "Maths")
    assert row.entered == 1, "only the fully-marked pupil is counted"
    assert row.incomplete == 1
    assert row.failed == 0, "the incomplete pupil must not be counted as failing"


# ── the three states stay distinct ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_term_with_no_setup_says_so_on_all_three(db, org):
    """An empty report that means "nobody qualified" and one that means "the term
    was never set up" look identical on a page. Only one is a reason to worry."""
    await _bands(db, org)
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary", org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Summer", org_id=org.id)
    full = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    db.add_all([cls, term, full])
    await db.commit()
    admin = await _admin(db, org)

    for fn in (order_of_merit, grade_summary, subject_performance):
        res = await fn(term_id=term.id, sub_term_id=full.id, class_id=cls.id,
                       db=db, current_user=admin)
        assert res.not_configured is True, f"{fn.__name__} must say the term is unset"


# ── Departmental Analysis ─────────────────────────────────────────────────────

async def _with_departments(db, org, mapping: dict[str, str | None], marks: dict):
    """A world whose subjects carry departments. `mapping` is subject -> department
    (None meaning deliberately unassigned)."""
    w = await _world(db, org, marks=marks)
    for name, dept in mapping.items():
        w["subjects"][name].department = dept
    await db.commit()
    return w


@pytest.mark.asyncio
async def test_departmental_groups_subjects_and_averages_them(db, org):
    from app.routers.modules.platform import departmental_analysis

    w = await _with_departments(
        db, org,
        {"Maths": "Mathematics", "Physics": "Sciences", "Chemistry": "Sciences"},
        marks={"Ada Obi": {"Maths": 80, "Physics": 60, "Chemistry": 40},
               "Bode Ade": {"Maths": 60, "Physics": 40, "Chemistry": 20}})
    admin = await _admin(db, org)
    res = await departmental_analysis(term_id=w["term"].id, sub_term_id=w["full"].id,
                                      class_id=w["cls"].id, db=db, current_user=admin)

    by_dept = {r.department: r for r in res.rows}
    assert set(by_dept) == {"Mathematics", "Sciences"}
    sciences = by_dept["Sciences"]
    assert sorted(sciences.subjects) == ["Chemistry", "Physics"]
    assert sciences.entered == 4, "two pupils x two subjects"
    assert sciences.pupils == 2, "distinct pupils, not marks"
    assert float(sciences.average) == 40.0    # (60+40+40+20)/4
    assert float(sciences.highest) == 60.0 and float(sciences.lowest) == 20.0
    assert res.no_departments is False


@pytest.mark.asyncio
async def test_an_unassigned_subject_gets_its_own_row_and_sorts_last(db, org):
    """A report whose totals quietly exclude a subject is worse than one that
    shows the gap."""
    from app.routers.modules.platform import departmental_analysis

    w = await _with_departments(
        db, org, {"Maths": "Mathematics", "Physics": None},
        marks={"Ada Obi": {"Maths": 80, "Physics": 60}})
    admin = await _admin(db, org)
    res = await departmental_analysis(term_id=w["term"].id, sub_term_id=w["full"].id,
                                      class_id=w["cls"].id, db=db, current_user=admin)

    assert [r.department for r in res.rows] == ["Mathematics", None], "unassigned last"
    unassigned = res.rows[-1]
    assert unassigned.subjects == ["Physics"]
    assert unassigned.entered == 1
    total = sum(r.entered for r in res.rows)
    assert total == 2, "every mark is counted somewhere"


@pytest.mark.asyncio
async def test_no_departments_is_distinct_from_not_configured(db, org):
    """Both render an empty page; only one means the term was never set up."""
    from app.routers.modules.platform import departmental_analysis

    w = await _with_departments(db, org, {"Maths": None},
                                marks={"Ada Obi": {"Maths": 80}})
    admin = await _admin(db, org)
    res = await departmental_analysis(term_id=w["term"].id, sub_term_id=w["full"].id,
                                      class_id=w["cls"].id, db=db, current_user=admin)
    assert res.no_departments is True, "nothing is categorised"
    assert res.not_configured is False, "but the term IS set up"
    assert res.rows, "and the marks still appear, under the unassigned row"


@pytest.mark.asyncio
async def test_departmental_excludes_a_partially_marked_pupil(db, org):
    """Same rule as Subject Performance: a department mean dragged down by a CA
    nobody entered misreports the department, not the pupil."""
    from app.routers.modules.platform import departmental_analysis

    w = await _world(db, org, weighted=True,
                     marks={"Ada Obi": {"Maths": 90}, "Bode Ade": {"Maths": 60}})
    w["subjects"]["Maths"].department = "Mathematics"
    await db.commit()
    db.add(StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=w["pupils"]["Ada Obi"].id,
        subject_id=w["subjects"]["Maths"].id, assessment_id=w["ca"].id,
        score=40, org_id=org.id))
    await db.commit()
    admin = await _admin(db, org)

    res = await departmental_analysis(term_id=w["term"].id, sub_term_id=w["full"].id,
                                      class_id=w["cls"].id, db=db, current_user=admin)
    row = next(r for r in res.rows if r.department == "Mathematics")
    assert row.entered == 1, "only the fully-marked pupil counts"
    assert row.incomplete == 1
    assert row.failed == 0, "the incomplete pupil is not counted as failing"
