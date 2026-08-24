"""
CBT-to-Assessment sync service.

Provides a reusable, idempotent function to sync CBT exam results to
StudentAssessmentScore. Used by:
  1. publish_exam_results() endpoint (permanent hook for future exams)
  2. Backfill script (one-time migration of 120 existing exams)

The sync is idempotent: calling twice updates existing scores, never duplicates.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.school import (
    CBTExam, CBTAttempt, AttemptStatus,
)
from app.models.modules.platform import (
    Assessment, AssessmentGroup, StudentAssessmentScore,
)
from uuid import uuid4
from datetime import datetime


async def get_or_create_cbt_assessment(
    db: AsyncSession,
    org_id: str,
    term_id: str,
    sub_term_id: str,
) -> str | None:
    """
    Get or create the "CBT Exam Score" Assessment for a given term.

    Each term gets its own Assessment (required by schema: assessment.term_id FK).
    This ensures CBT scores for Term 1 don't collide with Term 2, etc.

    Returns Assessment ID or None if term/sub_term don't exist.
    """
    # Check: does assessment already exist for this term?
    existing = (await db.execute(
        select(Assessment).where(
            Assessment.org_id == org_id,
            Assessment.term_id == term_id,
            Assessment.sub_term_id == sub_term_id,
            Assessment.name == "CBT Exam Score",
        )
    )).scalar_one_or_none()

    if existing:
        return existing.id

    # Check: does the term/sub-term exist? (validation)
    from app.models.modules.platform import AcademicTerm, AcademicSubTerm
    term_row = (await db.execute(
        select(AcademicTerm).where(AcademicTerm.id == term_id)
    )).scalar_one_or_none()
    sub_term_row = (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.id == sub_term_id)
    )).scalar_one_or_none()

    if not term_row or not sub_term_row:
        return None  # Can't create assessment without valid term/sub_term

    # Create AssessmentGroup if needed (one per org, reused by all CBT assessments)
    group = (await db.execute(
        select(AssessmentGroup).where(
            AssessmentGroup.org_id == org_id,
            AssessmentGroup.name == "CBT Exam Scores",
        )
    )).scalar_one_or_none()

    if not group:
        group = AssessmentGroup(
            id=str(uuid4()),
            org_id=org_id,
            name="CBT Exam Scores",
            position=0,
        )
        db.add(group)
        await db.flush()

    # Create Assessment for this term
    assessment = Assessment(
        id=str(uuid4()),
        org_id=org_id,
        group_id=group.id,
        name="CBT Exam Score",
        code="CBT",
        max_score=100,
        term_id=term_id,
        sub_term_id=sub_term_id,
        year_group=None,  # All levels
        decimal_places=0,
        position=0,
    )
    db.add(assessment)
    await db.flush()
    return assessment.id


async def sync_cbt_to_assessment_score(
    db: AsyncSession,
    exam_id: str,
    org_id: str,
) -> tuple[int, str | None]:
    """
    Sync one exam's CBT results to StudentAssessmentScore.

    For each student with a best GRADED attempt:
    - Compute percentage score (0-100)
    - Create or UPDATE StudentAssessmentScore

    Idempotent: calling twice updates existing rows, never creates duplicates.

    Args:
        db: AsyncSession
        exam_id: CBTExam ID
        org_id: Organization ID

    Returns:
        (row_count, error_reason)
        - row_count: number of StudentAssessmentScore rows created/updated
        - error_reason: None if success, else a string explaining why sync was skipped
    """
    exam = (await db.execute(
        select(CBTExam).where(CBTExam.id == exam_id, CBTExam.org_id == org_id)
    )).scalar_one_or_none()

    if not exam:
        return 0, "Exam not found"

    if not exam.subject_id:
        return 0, "Exam has no subject assigned"

    if not exam.term:
        return 0, "Exam has no term assigned"

    if not exam.results_published_at:
        return 0, "Exam results not published yet"

    # Look up AcademicTerm by exam.term name
    from app.models.modules.platform import AcademicTerm, AcademicSubTerm

    term_row = (await db.execute(
        select(AcademicTerm).where(
            AcademicTerm.org_id == org_id,
            AcademicTerm.name == exam.term,
        )
    )).scalar_one_or_none()

    if not term_row:
        return 0, f"No AcademicTerm found for '{exam.term}'"

    # Find a sub-term (org-wide, not tied to specific term).
    # Most assessments use "Full-Term"; fall back to any sub-term.
    sub_term_row = (await db.execute(
        select(AcademicSubTerm).where(
            AcademicSubTerm.org_id == org_id,
            AcademicSubTerm.name.in_(["Full-Term", "Full Term"]),
        )
    )).scalar_one_or_none()

    if not sub_term_row:
        # Fall back to any sub-term
        sub_term_row = (await db.execute(
            select(AcademicSubTerm).where(
                AcademicSubTerm.org_id == org_id,
            )
        )).scalar_one_or_none()

    if not sub_term_row:
        return 0, f"No sub-term found in organization"

    # Get or create the Assessment for this exam's term
    assessment_id = await get_or_create_cbt_assessment(
        db, org_id, term_row.id, sub_term_row.id
    )
    if not assessment_id:
        return 0, "Could not create Assessment for exam's term"

    # Get best attempt per student. superseded_at IS NULL = active — the same
    # filter cbt.py's _active() applies (inlined here: importing the router back
    # into this service would be circular).
    attempts = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.exam_id == exam_id,
            CBTAttempt.org_id == org_id,
            CBTAttempt.status == AttemptStatus.GRADED,
            CBTAttempt.superseded_at.is_(None),
        )
    )).scalars().all()

    best: dict[str, tuple[CBTAttempt, float]] = {}
    for a in attempts:
        mx = float(a.max_score or 0)
        pct = (float(a.score or 0) / mx * 100) if mx > 0 else 0.0
        cur = best.get(a.student_id)
        if cur is None or pct > cur[1]:
            best[a.student_id] = (a, pct)

    if not best:
        return 0, None  # No graded attempts; not an error

    # Get existing StudentAssessmentScore rows for this assessment + subject
    existing = {
        (r.student_id, r.subject_id): r
        for r in (await db.execute(
            select(StudentAssessmentScore).where(
                StudentAssessmentScore.assessment_id == assessment_id,
                StudentAssessmentScore.subject_id == exam.subject_id,
                StudentAssessmentScore.org_id == org_id,
            )
        )).scalars().all()
    }

    written = 0
    for student_id, (_attempt, raw_pct) in best.items():
        pct = round(raw_pct, 2)
        key = (student_id, exam.subject_id)
        existing_score = existing.get(key)

        if existing_score:
            # UPDATE: idempotent, safe if called twice
            existing_score.score = pct
        else:
            # CREATE: first time
            db.add(StudentAssessmentScore(
                id=str(uuid4()),
                student_id=student_id,
                subject_id=exam.subject_id,
                assessment_id=assessment_id,
                score=pct,
                org_id=org_id,
            ))
        written += 1

    await db.flush()
    return written, None
