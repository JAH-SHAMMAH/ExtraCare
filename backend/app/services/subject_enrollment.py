"""Subject enrolment: the gate on mark entry, and the backfill that seeds it.

THE RULE: no mark may be entered for a (pupil, subject) pair without a
StudentSubjectEnrollment row for the current academic session.

WHERE IT IS ENFORCED, and where it deliberately is not:

  * Report Entry grid (save)   -> BLOCKED, and the grid itself is filtered so a
                                  teacher is never shown a pupil they cannot save.
  * Reports Upload (bulk file) -> per-row error, matching that endpoint's
                                  existing non-fatal error list.
  * CBT -> assessment sync     -> NOT blocked. A pupil who sat the exam
                                  demonstrably takes the subject; discarding a
                                  real result over a missing checkbox would put
                                  the error on a child's report card. The
                                  discrepancy is reported instead.

``plan_backfill`` is FROZEN for migration 128's sake: the dry-run script and the
migration both call it, so what the script previews is exactly what the migration
applies. Change what it selects and you change what an already-shipped migration
would do on a fresh database. New behaviour belongs in a new module and a new
revision.
"""
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


# ── session resolution ───────────────────────────────────────────────────────

class AcademicYearUnresolved(Exception):
    """No academic session could be resolved, so enrolment cannot be checked.

    Raised rather than silently skipping the gate. A gate that quietly turns
    itself off is worse than one that refuses: the refusal names its own fix,
    while the silence lets unenrolled marks through unnoticed.
    """


async def resolve_academic_year(db: AsyncSession, org_id: str) -> str:
    """The session string enrolment is keyed on, e.g. "2025/2026".

    Prefers the session flagged current. Falls back to the only session when
    exactly one exists, so a school that never set the flag still works. Raises
    when it genuinely cannot tell, because guessing would split enrolments across
    two different year strings and the gate would then refuse marks for reasons
    nobody could see.
    """
    from app.models.modules.platform import AcademicSession

    cur = (await db.execute(
        select(AcademicSession).where(
            AcademicSession.org_id == org_id,
            AcademicSession.is_current == True,  # noqa: E712
        )
    )).scalars().first()
    if cur and (cur.name or "").strip():
        return cur.name.strip()

    rows = (await db.execute(
        select(AcademicSession).where(AcademicSession.org_id == org_id)
    )).scalars().all()
    named = [r for r in rows if (r.name or "").strip()]
    if len(named) == 1:
        return named[0].name.strip()

    raise AcademicYearUnresolved(
        "No current academic session is set, so subject enrolment cannot be "
        "checked. Ask an administrator to mark a session as current under "
        "School Setup."
    )


# ── the gate ─────────────────────────────────────────────────────────────────

async def resolve_academic_year_for_check(db: AsyncSession, org_id: str) -> str | None:
    """`resolve_academic_year`, but None instead of raising — for READING the gate.

    WHY THE SPLIT. Writing an enrolment needs a concrete year, so the write paths
    keep the raising version: you cannot record "enrolled" without saying when.
    CHECKING one does not. Making mark entry depend on a configured session would
    couple a core teacher workflow to a School Setup flag that has nothing to do
    with enrolment — miss the `is_current` flag when adding next year's session and
    every teacher in the school stops being able to save marks, with an error
    message about enrolment that names the wrong problem.

    Callers pass the None straight through to `enrolled_student_ids`, which then
    checks enrolment in ANY year. The gate stays ON — an unenrolled pupil is still
    refused — it just stops insisting it knows which session it is. That is
    strictly safer than the two alternatives: refusing all marks, or silently
    switching the gate off.
    """
    try:
        return await resolve_academic_year(db, org_id)
    except AcademicYearUnresolved:
        return None


async def enrolled_student_ids(
    db: AsyncSession, org_id: str, subject_id: str, academic_year: str | None,
    student_ids: list[str] | None = None,
) -> set[str]:
    """Which of `student_ids` are enrolled in `subject_id`.

    `academic_year=None` means "any year" — the degraded mode described in
    `resolve_academic_year_for_check`. Enrolment is still required; only the
    session narrowing is dropped.

    Returns a set so callers can filter a grid or validate a batch with one query
    rather than one per pupil — the entry grid saves a whole class at once and an
    N+1 there would be felt.
    """
    from app.models.modules.academics import StudentSubjectEnrollment

    q = select(StudentSubjectEnrollment.student_id).where(
        StudentSubjectEnrollment.org_id == org_id,
        StudentSubjectEnrollment.subject_id == subject_id,
    )
    if academic_year is not None:
        q = q.where(StudentSubjectEnrollment.academic_year == academic_year)
    if student_ids:
        q = q.where(StudentSubjectEnrollment.student_id.in_(student_ids))
    return set((await db.execute(q)).scalars().all())


async def enrolled_subject_ids(
    db: AsyncSession, org_id: str, student_id: str, academic_year: str,
) -> set[str]:
    """Which subjects one pupil is enrolled in this session."""
    from app.models.modules.academics import StudentSubjectEnrollment

    return set((await db.execute(
        select(StudentSubjectEnrollment.subject_id).where(
            StudentSubjectEnrollment.org_id == org_id,
            StudentSubjectEnrollment.student_id == student_id,
            StudentSubjectEnrollment.academic_year == academic_year,
        )
    )).scalars().all())


def not_enrolled_message(subject_name: str | None, n: int) -> str:
    subj = subject_name or "this subject"
    if n == 1:
        return (f"1 pupil is not enrolled in {subj}, so their marks were not "
                f"saved. Enrol them under Subject Enrollment first.")
    return (f"{n} pupils are not enrolled in {subj}, so their marks were not "
            f"saved. Enrol them under Subject Enrollment first.")


# ── the backfill (FROZEN — migration 128 depends on this) ────────────────────

BACKFILL_SQL = text("""
    SELECT DISTINCT student_id, subject_id FROM student_assessment_scores
     WHERE org_id = :org
    UNION
    SELECT DISTINCT student_id, subject_id FROM grades
     WHERE org_id = :org
""")


async def plan_backfill(db: AsyncSession, org_id: str, academic_year: str) -> list[tuple[str, str]]:
    """The (student_id, subject_id) pairs to enrol, from marks that already exist.

    WHY THE UNION OF BOTH MARK STORES. `student_assessment_scores` is the new
    report engine's store; `grades` is the older gradebook. At Fairview they were
    1,799 and 1,800 pairs, and the one pair only in `grades` was a real pupil —
    FSN-0031 Musa Yusuf, Biology — whose assessment-score row was lost when a CBT
    re-sync dropped mid-run. Backfilling from the new store alone would have left
    him unenrolled in a subject he has a grade for: a one-pupil bug, invisible
    until someone questioned his report card.

    An existing mark IS the evidence of enrolment. Without this backfill every
    mark already in the system becomes uneditable the moment the gate ships,
    because re-saving an existing mark would be refused.

    Pairs already enrolled for `academic_year` are excluded, so this is
    idempotent — running it twice creates nothing.
    """
    from app.models.modules.academics import StudentSubjectEnrollment

    pairs = {(r[0], r[1]) for r in (await db.execute(BACKFILL_SQL, {"org": org_id})).all()}

    already = {(r[0], r[1]) for r in (await db.execute(
        select(StudentSubjectEnrollment.student_id, StudentSubjectEnrollment.subject_id)
        .where(StudentSubjectEnrollment.org_id == org_id,
               StudentSubjectEnrollment.academic_year == academic_year)
    )).all()}

    return sorted(pairs - already)
