"""Carry the marks already in the portal onto Fairview's new card columns.

WHY THIS EXISTS. The portal holds marks entered against the OLD all-level columns
(a single percentage-style component per subject). The cards now print Fairview's
real columns -- Secondary CA 1 / CA 2 / EXAM, Junior CA 1 / PRJ / C.E / EXAM -- so
those marks have to land there or every existing pupil shows an empty table.

THE HONEST LIMIT. An old mark is ONE number out of 100; it does not say how much of
it was test, project or exam. So the split is PROPORTIONAL: each component gets the
same fraction of its maximum as the pupil's old percentage (a 74% pupil gets 74% of
CA 1, 74% of PRJ, ...), with the exam taking the rounding remainder so the total is
exactly the old percentage rounded. Totals, grades and positions therefore come out
the same as before. It is a placeholder for the real component marks and is meant
for the portal's current test data; teachers overwrite it when they enter real marks.

NEVER DESTRUCTIVE. It only fills component scores that do not exist yet, and the
old columns are RETIRED (year_group set to 'LEGACY'), not deleted, with every old
score left in place. Setting year_group back to NULL undoes it.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.platform import (
    AcademicSession, AcademicSubTerm, Assessment, Cumulative, SchoolSection,
    StudentAssessmentScore,
)
from app.models.modules.school import SchoolClass, Student
from app.services.report_sections import report_keys_for

LEGACY = "LEGACY"
SUB_TERM = "Full-Term"
# component names per template, and which one absorbs the rounding remainder
TARGET = {
    "secondary-report": (["CA 1", "CA 2", "EXAM"], "EXAM"),
    "junior-report": (["CA 1", "PRJ", "C.E", "EXAM"], "EXAM"),
}


def _r0(x: Decimal) -> Decimal:
    return x.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def split_percentage(pct: Decimal, maxes: dict[str, Decimal], remainder: str) -> dict[str, Decimal]:
    """Proportional split of a 0-100 percentage over components; exact total."""
    total = _r0(pct)
    out = {n: _r0(pct * m / Decimal(100)) for n, m in maxes.items() if n != remainder}
    out[remainder] = min(max(total - sum(out.values()), Decimal(0)), maxes[remainder])
    return out


async def align_legacy_marks(db: AsyncSession, org_id: str, write: bool, retire: bool = True) -> dict:
    res = {"pupils_subjects": 0, "scores_added": 0, "already_there": 0, "no_target": 0,
           "legacy_assessments": 0, "legacy_cumulatives": 0, "retired": False, "problems": []}
    sess = (await db.execute(select(AcademicSession).where(
        AcademicSession.org_id == org_id, AcademicSession.is_current == True))).scalars().first()  # noqa: E712
    sub = (await db.execute(select(AcademicSubTerm).where(
        AcademicSubTerm.org_id == org_id, AcademicSubTerm.name == SUB_TERM))).scalars().first()
    if not sess or not sub:
        res["problems"].append("needs a current session and a Full-Term sub-term")
        return res

    legacy = (await db.execute(select(Assessment).where(
        Assessment.org_id == org_id, Assessment.session_id == sess.id,
        Assessment.year_group.is_(None)))).scalars().all()
    legacy_cums = (await db.execute(select(Cumulative).where(
        Cumulative.org_id == org_id, Cumulative.session_id == sess.id,
        Cumulative.year_group.is_(None)))).scalars().all()
    res["legacy_assessments"], res["legacy_cumulatives"] = len(legacy), len(legacy_cums)
    if not legacy:
        return res
    by_id = {a.id: a for a in legacy}

    secs = (await db.execute(select(SchoolSection).where(SchoolSection.org_id == org_id))).scalars().all()
    keys = report_keys_for(secs)
    classes = {c.id: c for c in (await db.execute(
        select(SchoolClass).where(SchoolClass.org_id == org_id))).scalars().all()}
    students = {s.id: s for s in (await db.execute(
        select(Student).where(Student.org_id == org_id))).scalars().all()}

    # new component assessments: (term, year group) -> {name: Assessment}
    new: dict[tuple, dict[str, Assessment]] = defaultdict(dict)
    for a in (await db.execute(select(Assessment).where(
            Assessment.org_id == org_id, Assessment.session_id == sess.id,
            Assessment.sub_term_id == sub.id, Assessment.year_group.is_not(None)))).scalars().all():
        if (a.year_group or "").upper() != LEGACY:
            new[(a.term_id, a.year_group.upper())][a.name] = a

    scores = (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org_id,
        StudentAssessmentScore.assessment_id.in_(list(by_id))))).scalars().all()
    # (student, subject, term) -> [sum scores, sum maxes] over components actually scored
    agg: dict[tuple, list] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for sc in scores:
        if sc.score is None:
            continue
        a = by_id[sc.assessment_id]
        cell = agg[(sc.student_id, sc.subject_id, a.term_id)]
        cell[0] += Decimal(str(sc.score))
        cell[1] += Decimal(str(a.max_score))

    existing = {(s.student_id, s.subject_id, s.assessment_id) for s in (await db.execute(
        select(StudentAssessmentScore).where(StudentAssessmentScore.org_id == org_id,
            StudentAssessmentScore.assessment_id.in_(
                [a.id for d in new.values() for a in d.values()] or ["-"])))).scalars().all()}

    for (sid, subj, term_id), (got, mx) in agg.items():
        st = students.get(sid)
        cls = classes.get(st.class_id) if st else None
        key = keys.get(cls.section_id) if cls and cls.section_id else None
        spec = TARGET.get(key or "")
        comps = new.get((term_id, (cls.level or "").strip().upper())) if (cls and spec) else None
        if not spec or mx <= 0:
            res["no_target"] += 1
            continue
        if not comps or any(n not in comps for n in spec[0]):
            if write:                       # columns should exist by now
                res["no_target"] += 1
            else:                           # preview: they will be created first
                res["pupils_subjects"] += 1
                res["scores_added"] += len(spec[0])
            continue
        res["pupils_subjects"] += 1
        parts = split_percentage(got / mx * 100, {n: Decimal(str(comps[n].max_score)) for n in spec[0]}, spec[1])
        for name, val in parts.items():
            a = comps[name]
            if (sid, subj, a.id) in existing:
                res["already_there"] += 1
                continue
            res["scores_added"] += 1
            if write:
                db.add(StudentAssessmentScore(student_id=sid, subject_id=subj, assessment_id=a.id,
                                              score=val, org_id=org_id, source="align"))
                existing.add((sid, subj, a.id))

    # Hide the old columns only when EVERY legacy mark found a home; otherwise some
    # pupil's card would lose its only columns.
    if retire and res["no_target"] == 0 and (res["scores_added"] or res["already_there"]):
        res["retired"] = True
        if write:
            for row in [*legacy, *legacy_cums]:
                row.year_group = LEGACY
    elif retire and res["no_target"]:
        res["problems"].append(
            f"{res['no_target']} pupil-subject marks have no matching new column (class without a "
            "section or level), so the old columns were left visible.")
    if write:
        await db.flush()
    return res
