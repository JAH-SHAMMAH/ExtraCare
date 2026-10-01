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
    # Subjects the pupil HAS marks in, but not all the components the term's total
    # needs. Deliberately separate from `subject_pct`: their standing is unknown,
    # not low, and a report that ranks them would be ranking a gap in the register.
    incomplete_subjects: list[str] = field(default_factory=list)

    @property
    def subjects_counted(self) -> int:
        return len(self.subject_pct)


@dataclass
class TermAnalysis:
    term_name: str | None
    sub_term_name: str | None
    pupils: list[PupilResult] = field(default_factory=list)
    subject_names: dict[str, str] = field(default_factory=dict)
    # subject_id -> department, carried here because the Subject rows are already
    # loaded for their names. Departmental Analysis groups on it rather than
    # re-querying, and a subject with no department maps to None rather than being
    # dropped — "unassigned" is a real state a report should be able to show.
    subject_departments: dict[str, str | None] = field(default_factory=dict)
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
    session_id: str | None = None,
) -> TermAnalysis:
    """Every pupil's per-subject percentage and average for a (term, sub-term).

    `class_id` / `section_id` narrow the scope; omitting both analyses the school.

    A pupil with no marks is INCLUDED with `average=None` rather than dropped or
    scored zero. Which of those a report wants differs — Remedial List must not
    brand an unmarked child as failing, while an Order of Merit should simply not
    rank them — and that is the caller's decision to make, not this function's.
    """
    from app.models.modules.platform import (
        AcademicSubTerm, AcademicTerm, GradingBand, GradingScale,
        StudentAssessmentScore,
    )
    from app.models.modules.school import SchoolClass, Student, Subject
    from app.routers.modules.platform import _grade_for, _pick_display_cumulative
    from app.services.report_engine import evaluate_cumulative, is_fully_marked
    from app.services.session_scope import load_term_setup, resolve_session_id

    term_name = (await db.execute(select(AcademicTerm.name).where(
        AcademicTerm.id == term_id, AcademicTerm.org_id == org_id))).scalar_one_or_none()
    sub_name = (await db.execute(select(AcademicSubTerm.name).where(
        AcademicSubTerm.id == sub_term_id, AcademicSubTerm.org_id == org_id))).scalar_one_or_none()

    out = TermAnalysis(term_name=term_name, sub_term_name=sub_name)

    # ── config, loaded once ───────────────────────────────────────────────────
    # Session-scoped (migration 134). `session_id` of None means no year could be
    # resolved, and `load_term_setup` returns empty for that rather than reading
    # every year at once — which lands on `not_configured` below.
    # An omitted session means "the current one", never "every year at once":
    # a caller that forgets should get this year's answer, not an empty one that
    # reads as "nothing is configured".
    if session_id is None:
        session_id = await resolve_session_id(db, org_id)
    setup = await load_term_setup(db, org_id, session_id, term_id)
    assessments = setup.assessments
    cumulatives = setup.cumulatives
    display = _pick_display_cumulative(cumulatives, sub_term_id)
    if not display or not assessments:
        # Nothing to compute from. Said explicitly, because a report rendering
        # "everyone scored 0" here would be a confident lie — it is the same
        # empty-cumulative condition that made every subject grade F.
        out.not_configured = True
        return out

    cumul_by_id = setup.cumul_by_id
    components = setup.components

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

    subject_rows = (await db.execute(select(Subject).where(
        Subject.org_id == org_id,
        Subject.id.in_(list(subj_ids) or ["_none_"])))).scalars().all()
    out.subject_names = {s.id: s.name for s in subject_rows}
    out.subject_departments = {s.id: s.department for s in subject_rows}

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
            # A PARTIALLY marked subject is not scored. `evaluate_cumulative` reads
            # a missing component as zero, so a pupil with an exam mark and no CA
            # would compute to 60% of their real standing — and this function feeds
            # the Booster List, which would then name them as failing because of a
            # mark their teacher has not entered yet. Counted as incomplete instead,
            # which is what it is.
            if not is_fully_marked(display.id, cumul_by_id, components, assessments, scores):
                pupil.incomplete_subjects.append(sid)
                continue
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


# ── across SESSIONS ──────────────────────────────────────────────────────────
#
# Everything above answers "how did this (term, sub-term) go". This answers a
# question that needed migration 134 before it could be asked at all: how has a
# subject moved from one YEAR to the next. Terms are shared across sessions, so
# until assessments carried a session_id there was no way to separate 2025/2026's
# Autumn from 2026/2027's, and any such figure would silently have been a blend.


@dataclass
class SessionSubjectCell:
    """One subject's standing in one session."""
    average: Decimal | None = None
    # How many of the session's terms produced a figure for this subject. Carried
    # because a mean over ONE term is not a year, and the two are
    # indistinguishable once reduced to a single number.
    terms_counted: int = 0
    entered: int = 0                  # marks that fed it, across those terms


@dataclass
class SessionColumn:
    session_id: str
    session_name: str | None
    is_current: bool = False
    # Terms of this session that were computable for the chosen sub-term. 0 means
    # the year is not set up for it, which is a different statement from "set up
    # and everyone scored nothing".
    terms_counted: int = 0
    term_names: list[str] = field(default_factory=list)
    not_configured: bool = True


@dataclass
class SessionsAnalysis:
    sub_term_name: str | None = None
    columns: list[SessionColumn] = field(default_factory=list)
    # subject_id -> session_id -> cell
    cells: dict[str, dict[str, SessionSubjectCell]] = field(default_factory=dict)
    subject_names: dict[str, str] = field(default_factory=dict)
    subject_departments: dict[str, str | None] = field(default_factory=dict)


async def analyse_sessions(
    db: AsyncSession,
    org_id: str,
    sub_term_id: str,
    *,
    session_ids: list[str] | None = None,
    class_id: str | None = None,
    section_id: str | None = None,
) -> SessionsAnalysis:
    """Every subject's average in each session, for one sub-term.

    The sub-term is a PARAMETER, deliberately. Sniffing for a term named
    "Full-Term" would be the hardcoded-vs-configured mistake this codebase keeps
    removing, and `Mock` exists precisely so a school can compare mocks across
    years instead. Comparing like with like is the caller's statement to make.

    A session's figure is the unweighted mean of its TERMS' figures — the same
    convention `sessional_average` uses for a pupil's Sessional Score, so the two
    cannot disagree about what averaging a year means. A term that is unmarked or
    not configured contributes NOTHING rather than a zero: a year dragged down by
    a term nobody has taught yet would misreport the subject.

    Built on `analyse_term`, once per computable (session, term). Pairs with no
    cumulative of their own are skipped BEFORE the call — the same guard
    `performance_tracker` uses — because the cost here is sessions x terms full
    passes over every pupil, and most pairs are empty in a normal year.
    """
    from app.models.modules.platform import (
        AcademicSession, AcademicSubTerm, AcademicTerm, Cumulative,
    )

    sub_name = (await db.execute(select(AcademicSubTerm.name).where(
        AcademicSubTerm.id == sub_term_id,
        AcademicSubTerm.org_id == org_id))).scalar_one_or_none()
    out = SessionsAnalysis(sub_term_name=sub_name)

    q = select(AcademicSession).where(AcademicSession.org_id == org_id)
    if session_ids:
        q = q.where(AcademicSession.id.in_(session_ids))
    sessions = (await db.execute(q)).scalars().all()
    # Chronological, so the columns read left-to-right as the years ran and a
    # trend has an unambiguous direction. `name` is the tie-break because
    # start_date is optional — a session created for next year legitimately has
    # no dates yet.
    sessions = sorted(sessions, key=lambda s: (s.start_date is None,
                                               s.start_date, s.name or ""))

    terms = (await db.execute(select(AcademicTerm).where(
        AcademicTerm.org_id == org_id).order_by(
        AcademicTerm.position, AcademicTerm.name))).scalars().all()

    # (session, term) pairs that own a cumulative for THIS sub-term.
    configured = {
        (c.session_id, c.term_id)
        for c in (await db.execute(select(Cumulative).where(
            Cumulative.org_id == org_id,
            Cumulative.sub_term_id == sub_term_id))).scalars().all()
    }

    for s in sessions:
        col = SessionColumn(session_id=s.id, session_name=s.name,
                            is_current=bool(s.is_current))
        # subject_id -> list of per-term averages, and the marks behind them
        per_subject: dict[str, list[Decimal]] = {}
        per_subject_entered: dict[str, int] = {}

        for t in terms:
            if (s.id, t.id) not in configured:
                continue
            a = await analyse_term(db, org_id, t.id, sub_term_id,
                                   class_id=class_id, section_id=section_id,
                                   session_id=s.id)
            if a.not_configured:
                continue
            out.subject_names.update(a.subject_names)
            out.subject_departments.update(a.subject_departments)

            # This term's average per subject, over the pupils who have a usable
            # mark in it. Partially-marked pupils are already excluded upstream.
            term_vals: dict[str, list[Decimal]] = {}
            for p in a.pupils:
                for subj_id, pct in p.subject_pct.items():
                    term_vals.setdefault(subj_id, []).append(pct)
            if not term_vals:
                continue            # configured, taught, but nothing entered yet
            col.terms_counted += 1
            col.term_names.append(t.name or "")
            for subj_id, vals in term_vals.items():
                per_subject.setdefault(subj_id, []).append(
                    sum(vals) / Decimal(len(vals)))
                per_subject_entered[subj_id] = (
                    per_subject_entered.get(subj_id, 0) + len(vals))

        col.not_configured = col.terms_counted == 0
        out.columns.append(col)

        for subj_id, term_avgs in per_subject.items():
            out.cells.setdefault(subj_id, {})[s.id] = SessionSubjectCell(
                average=sum(term_avgs) / Decimal(len(term_avgs)),
                terms_counted=len(term_avgs),
                entered=per_subject_entered.get(subj_id, 0))

    return out
