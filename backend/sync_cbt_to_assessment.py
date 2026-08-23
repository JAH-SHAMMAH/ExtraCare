#!/usr/bin/env python
"""
Reusable function to sync CBT exam results to StudentAssessmentScore.

This function is designed to be called:
1. From publish_exam_results()/_feed_gradebook() (permanent hook for future exams)
2. From a backfill script looping over existing exams
3. From a dry-run script to count rows

The sync is idempotent: calling twice on the same exam updates existing scores,
never creates duplicates.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.modules.school import CBTAttempt, Grade, AttemptStatus, Student
from app.models.modules.platform import StudentAssessmentScore, Assessment
from app.services.grading import grade_letter


async def sync_cbt_to_assessment_score(
    db: AsyncSession,
    exam_id: str,
    assessment_id: str,
    org_id: str,
    actor_id: str = None,
) -> int:
    """
    Sync one exam's CBT results to StudentAssessmentScore rows.

    For each student with a best GRADED attempt:
    - Compute percentage score (0-100)
    - Create or UPDATE StudentAssessmentScore

    Idempotent: calling twice updates existing rows, never creates duplicates.

    Args:
        db: AsyncSession
        exam_id: CBTExam ID
        assessment_id: Assessment ID (the "CBT Score" assessment)
        org_id: Organization ID
        actor_id: User ID of the syncer (for audits, optional)

    Returns:
        Count of StudentAssessmentScore rows created/updated
    """
    from app.models.modules.school import CBTExam

    exam = (await db.execute(
        select(CBTExam).where(CBTExam.id == exam_id, CBTExam.org_id == org_id)
    )).scalar_one_or_none()

    if not exam or not exam.subject_id:
        return 0  # Can't sync without subject_id

    # Get best attempt per student
    attempts = (await db.execute(
        select(CBTAttempt).where(
            CBTAttempt.exam_id == exam_id,
            CBTAttempt.org_id == org_id,
            CBTAttempt.status == AttemptStatus.GRADED,
            CBTAttempt.superseded.isnot(True),
        )
    )).scalars().all()

    best: dict[str, tuple[CBTAttempt, float]] = {}
    for a in attempts:
        mx = float(a.max_score or 0)
        pct = (float(a.score or 0) / mx * 100) if mx > 0 else 0.0
        cur = best.get(a.student_id)
        if cur is None or pct > cur[1]:
            best[a.student_id] = (a, pct)

    # Get existing StudentAssessmentScore rows for this exam's subject + assessment
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
                student_id=student_id,
                subject_id=exam.subject_id,
                assessment_id=assessment_id,
                score=pct,
                org_id=org_id,
            ))
        written += 1

    await db.flush()
    return written
