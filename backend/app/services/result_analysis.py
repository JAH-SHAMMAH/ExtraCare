"""The shared computation behind Result Analysis.

ONE core, many reports. Remedial List, Honour Roll, Order of Merit, the Grade
Summary Sheet and Subject Performance Analysis are all filters or aggregations over
the same thing: every pupil's per-subject percentage and overall average for a
(term, sub-term). Each of those computed independently would mean five near-identical
loops over the cumulative evaluator, which drift apart and disagree — and
`report_cards_bulk` already documents what re-running this per pupil costs.

So `analyse_term` does it ONCE, for a whole scope, and the reports read its result.

WHY NOT REUSE report_insight: that returns AGGREGATES (per-subject average, gender
split, per-class average) and has already thrown the per-pupil detail away. These
reports are about individual pupils, so they need the layer underneath it.

WHY NOT REUSE report_broadsheet: it is per-CLASS and carries presentation — band
legends, column definitions, submission state. Result Analysis is school-wide and
wants the numbers alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PupilResult:
    """One pupil's computed standing for the scope."""
    student_id: str
    student_name: str
    admission_no: str | None
    class_id: str | None
    class_name: str | None
    # subject_id -> percentage (0-100), only for subjects the pupil has marks in
    subject_pct: dict[str, Decimal] = field(default_factory=dict)
    average: Decimal | None = None      # mean of the above; None when unmarked
    grade: str | None = None

    @property
    def subjects_counted(self) -> int:
        return len(self.subject_pct)


@dataclass
class TermAnalysis:
    term_name: str | None
    sub_term_name: str | None
    pupils: list[PupilResult] = field(default_factory=list)
    subject_names: dict[str, str] = field(default_factory=dict)
    # True when no display cumulative or no assessments exist for the term, i.e.
    # nothing is computable. Distinguished from "computed, and everyone scored
    # nothing" — the two look identical in a list of zeros and are not the same.
    not_configured: bool = False


async def analyse_term(
    db: AsyncSession,
    org_id: str,
    term_id: str,
    sub_term_id: str,
    *,
    class_id: str | None = None,
    section_id: str | None = None,
) -> TermAnalysis:
    """Every pupil's per-subject percentage and average for a (term, sub-term).

    `class_id` / `section_id` narrow the scope; omitting both analyses the school.

    A pupil with no marks is INCLUDED with `average=None` rather than dropped or
    scored zero. Which of those a report wants differs — Remedial List must not
    brand an unmarked child as failing, while an Order of Merit should simply not
    rank them — and that is the caller's decision to make, not this function's.
    """
    from app.models.modules.platform import (
        AcademicSubTerm, AcademicTerm, Assessment, Cumulative, CumulativeComponent,
        GradingBand, GradingScale, StudentAssessmentScore,
    )
    from app.models.modules.school import SchoolClass, Student, Subject
    from app.routers.modules.platform import _grade_for, _pick_display_cumulative
    from app.services.report_engine import evaluate_cumulative

    term_name = (await db.execute(select(AcademicTerm.name).where(
        AcademicTerm.id == term_id, AcademicTerm.org_id == org_id))).scalar_one_or_none()
    sub_name = (await db.execute(select(AcademicSubTerm.name).where(
        AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org_id))).scalar_one_or_none()

    out = TermAnalysis(term_name=term_name, sub_term_name=sub_name)

    # ── config, loaded once ───────────────────────────────────────────────────
    assessments = {a.id: a for a in (await db.execute(select(Assessment).where(
        Assessment.org_id == org_id, Assessment.term_id == term_id))).scalars().all()}
    cumulatives = (await db.execute(select(Cumulative).where(
        Cumulative.org_id == org_id, Cumulative.term_id == term_id))).scalars().all()
    display = _pick_display_cumulative(cumulatives, sub_term_id)
    if not display or not assessments:
        # Nothing to compute from. Said explicitly, because a report rendering
        # "everyone scored 0" here would be a confident lie — it is the same
        # empty-cumulative condition that made every subject grade F.
        out.not_configured = True
        return out

    cumul_by_id = {c.id: c for c in cumulatives}
    components: dict[str, list] = {}
    for cr in (await db.execute(select(CumulativeComponent).where(
            CumulativeComponent.org_id == org_id)
            .order_by(CumulativeComponent.position))).scalars().all():
        components.setdefault(cr.cumulative_id, []).append((cr.ref_type, cr.ref_id))

    scale = (await db.execute(select(GradingScale).where(
        GradingScale.org_id == org_id, GradingScale.scale_type == "numeric",
        GradingScale.purpose == "grade").order_by(
        GradingScale.show_in_table.desc()))).scalars().first()
    bands = (await db.execute(select(GradingBand).where(
        GradingBand.scale_id == scale.id, GradingBand.org_id == org_id))).scalars().all() \
        if scale else []

    # ── the scope ────────────────────────────────────────────────────────────
    classes = {c.id: c for c in (await db.execute(select(SchoolClass).where(
        SchoolClass.org_id == org_id))).scalars().all()}
    q = select(Student).where(
        Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    if class_id:
        q = q.where(Student.class_id == class_id)
    elif section_id:
        in_section = [cid for cid, c in classes.items() if c.section_id == section_id]
        q = q.where(Student.class_id.in_(in_section or ["_none_"]))
    students = (await db.execute(q.order_by(Student.first_name, Student.last_name))).scalars().all()
    if not students:
        return out

    # ── the marks, in ONE query for the whole scope ──────────────────────────
    score_map: dict[tuple, object] = {}
    subj_ids: set[str] = set()
    for r in (await db.execute(select(StudentAssessmentScore).where(
        StudentAssessmentScore.org_id == org_id,
        StudentAssessmentScore.student_id.in_([s.id for s in students]),
        StudentAssessmentScore.assessment_id.in_(list(assessments.keys())),
    ))).scalars().all():
        score_map[(r.student_id, r.subject_id, r.assessment_id)] = r.score
        subj_ids.add(r.subject_id)

    out.subject_names = {s.id: s.name for s in (await db.execute(select(Subject).where(
        Subject.org_id == org_id,
        Subject.id.in_(list(subj_ids) or ["_none_"])))).scalars().all()}

    # ── evaluate ─────────────────────────────────────────────────────────────
    for st in students:
        pupil = PupilResult(
            student_id=st.id,
            student_name=f"{st.first_name} {st.last_name}".strip(),
            admission_no=st.student_id,
            class_id=st.class_id,
            class_name=(classes[st.class_id].name if st.class_id in classes else None),
        )
        for sid in subj_ids:
            if not any(score_map.get((st.id, sid, aid)) is not None for aid in assessments):
                continue
            scores = {aid: score_map.get((st.id, sid, aid)) for aid in assessments}
            val, mx = evaluate_cumulative(display.id, cumul_by_id, components, assessments, scores)
            if mx:
                pupil.subject_pct[sid] = val / mx * 100
        if pupil.subject_pct:
            pupil.average = sum(pupil.subject_pct.values()) / len(pupil.subject_pct)
            pupil.grade = _grade_for(pupil.average, bands)
        out.pupils.append(pupil)

    return out


# ── thresholds ───────────────────────────────────────────────────────────────

DEFAULT_PASSMARK = Decimal("40")
DEFAULT_HONOURS = Decimal("80")


async def resolve_thresholds(
    db: AsyncSession, org_id: str, sub_term_name: str | None,
) -> tuple[Decimal, Decimal, str]:
    """(passmark, honours, source) from ReportBranding.

    The passmark is sub-term aware: ReportBranding carries BOTH
    `full_term_passmark` and `mid_term_passmark`, and using one for both would make
    half of that configuration dead. A sub-term whose name reads half/mid takes the
    mid-term mark.

    `source` is 'configured' or 'default', and it is returned rather than hidden so
    a report can say which it used. A pupil listed as failing against a threshold
    nobody set is the kind of thing that should be visible on the page.
    """
    from app.models.modules.platform import ReportBranding

    br = (await db.execute(select(ReportBranding).where(
        ReportBranding.org_id == org_id))).scalars().first()
    if not br:
        return DEFAULT_PASSMARK, DEFAULT_HONOURS, "default"

    is_mid = "half" in (sub_term_name or "").lower() or "mid" in (sub_term_name or "").lower()
    pass_raw = br.mid_term_passmark if is_mid else br.full_term_passmark
    passmark = pass_raw if pass_raw is not None else DEFAULT_PASSMARK
    honours = br.min_average_honours if br.min_average_honours is not None else DEFAULT_HONOURS
    source = "configured" if (pass_raw is not None and br.min_average_honours is not None) \
        else "partial"
    return Decimal(str(passmark)), Decimal(str(honours)), source
