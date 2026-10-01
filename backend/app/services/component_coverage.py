"""Which marks a term's TOTAL still needs before a class can be published.

THE FAILURE THIS EXISTS TO PREVENT. `evaluate_cumulative` cannot tell "scored
zero" from "not marked": `_d(None)` is `Decimal(0)`, so an unmarked component
adds nothing to the numerator and its full `max_score` to the denominator. With
CA(40) + Exam(60) and no CA marks entered, a pupil who scored 100% on the exam
reads as 60% — a D — and the number is perfectly correct in the schema's terms
and false in the school's.

Measured on the Autumn data before this was written: applying those weights with
no CA marks moved 1,645 of 1,799 letters and turned 154 Fs into 989.

WHY AT THE PUBLISH GATE. A flag beside a printed grade is the first thing lost
when a card is exported, printed, or read quickly, and a parent seeing "60% D"
with a footnote still sees a D. The gate is the only place that stops the wrong
number reaching them at all. The flagging elsewhere is support, so the gap is
visible long before anyone reaches publish — not a substitute for this.

"REQUIRED COMPONENT" is derived, not declared: it is any assessment that is a
component of the term's display cumulative, directly or through a nested
cumulative. No new column, no per-assessment flag to keep in step with the
configuration it would describe.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class MissingMark:
    student_id: str
    student_name: str
    subject_id: str
    subject_name: str | None
    assessment_id: str
    assessment_name: str | None


@dataclass
class CoverageReport:
    """What is missing, and enough context to say so usefully."""
    missing: list[MissingMark] = field(default_factory=list)
    pupils_affected: set[str] = field(default_factory=set)
    # Component assessments the display cumulative depends on, by name.
    required: list[str] = field(default_factory=list)
    # True when the term has no display cumulative or no assessments at all. Then
    # there is nothing to be missing, and refusing would be nonsense.
    not_configured: bool = False

    @property
    def ok(self) -> bool:
        return not self.missing

    def message(self) -> str:
        """The refusal a person reads. Names the component, counts the gap, and
        shows a sample — a bare count sends someone hunting."""
        by_assessment: dict[str, int] = {}
        for m in self.missing:
            by_assessment[m.assessment_name or m.assessment_id] = (
                by_assessment.get(m.assessment_name or m.assessment_id, 0) + 1)
        parts = ", ".join(f"{n} missing {name}" for name, n in sorted(by_assessment.items()))
        sample = "; ".join(
            f"{m.student_name} — {m.subject_name or 'a subject'} ({m.assessment_name})"
            for m in self.missing[:3])
        return (
            f"This class cannot be published yet: {parts}, across "
            f"{len(self.pupils_affected)} pupil(s). "
            f"An unentered mark is counted as zero when the total is worked out, so "
            f"publishing now would show a mark below what these pupils actually earned. "
            f"For example: {sample}. "
            f"Enter the missing marks, or remove that component from the term's total."
        )


async def component_coverage(
    db: AsyncSession, org_id: str, term_id: str, sub_term_id: str, class_id: str,
    session_id: str | None = None,
) -> CoverageReport:
    """Every (pupil, subject) in `class_id` missing a required component mark.

    A pupil with NO marks at all in a subject is not reported: they have not been
    assessed in it, which is a different situation from a part-marked subject and
    is not fixed by entering one component. Reporting them would bury the real
    gaps under every subject a class does not take.
    """
    from app.models.modules.platform import StudentAssessmentScore
    from app.models.modules.school import Student, Subject
    from app.routers.modules.platform import _pick_display_cumulative
    from app.services.session_scope import load_term_setup, resolve_session_id

    out = CoverageReport()

    if session_id is None:                      # see analyse_term
        session_id = await resolve_session_id(db, org_id)
    setup = await load_term_setup(db, org_id, session_id, term_id)
    assessments = setup.assessments
    cumulatives = setup.cumulatives
    display = _pick_display_cumulative(cumulatives, sub_term_id)
    if not display or not assessments:
        out.not_configured = True
        return out

    comps = setup.components

    # Walk the tree: a TOTAL made of cumulatives depends on THEIR assessments.
    required: list[str] = []
    seen: set[str] = set()

    def walk(cid: str) -> None:
        if cid in seen:
            return                                  # cycle guard, as the evaluator has
        seen.add(cid)
        for ref_type, ref_id in comps.get(cid, []):
            if ref_type == "assessment":
                if ref_id in assessments and ref_id not in required:
                    required.append(ref_id)
            else:
                walk(ref_id)

    walk(display.id)
    out.required = [assessments[a].name for a in required if a in assessments]
    if not required:
        out.not_configured = True
        return out

    pupils = (await db.execute(select(Student).where(
        Student.org_id == org_id, Student.class_id == class_id,
        Student.is_deleted == False,  # noqa: E712
    ))).scalars().all()
    if not pupils:
        return out

    rows = (await db.execute(
        select(StudentAssessmentScore.student_id, StudentAssessmentScore.subject_id,
               StudentAssessmentScore.assessment_id)
        .where(StudentAssessmentScore.org_id == org_id,
               StudentAssessmentScore.student_id.in_([p.id for p in pupils]),
               StudentAssessmentScore.assessment_id.in_(required))
    )).all()
    have: dict[tuple[str, str], set[str]] = {}
    for sid, subj, aid in rows:
        have.setdefault((sid, subj), set()).add(aid)

    subject_names = {s.id: s.name for s in (await db.execute(select(Subject).where(
        Subject.org_id == org_id))).scalars().all()}

    for (sid, subj), got in sorted(have.items()):
        for aid in required:
            if aid in got:
                continue
            pupil = next((p for p in pupils if p.id == sid), None)
            out.missing.append(MissingMark(
                student_id=sid,
                student_name=f"{getattr(pupil, 'first_name', '')} "
                             f"{getattr(pupil, 'last_name', '')}".strip() or sid,
                subject_id=subj, subject_name=subject_names.get(subj),
                assessment_id=aid,
                assessment_name=getattr(assessments.get(aid), "name", None),
            ))
            out.pupils_affected.add(sid)
    return out
