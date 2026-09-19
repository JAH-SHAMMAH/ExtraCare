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


# Three of the reasons a sync is skipped describe the ORGANISATION's academic
# setup rather than anything about the exam: no AcademicTerm matching the exam's
# term name, no sub-term defined at all, or an Assessment that could not be built
# from them. A teacher holds neither the scope nor the context to act on those, so
# showing them "No sub-term found in organization" is noise that reads like an
# accusation and sends them hunting for a setting they cannot see. They get
# ADMIN_FIX_NOTICE instead. The precise text still reaches admins and the audit
# log, which is where it can actually be acted on.
ADMIN_FIX_NOTICE = (
    "CBT scores for this exam can't reach Make Report because of a problem with "
    "the school's term setup. Ask an administrator to check it — there's nothing "
    "to fix on your side."
)


class SyncBlock(str):
    """Why a CBT exam's scores are not flowing into Make Report.

    A `str` subclass rather than a dataclass so that every caller that already
    treats the reason as text keeps working untouched: the backfill scripts print
    it, the tests substring-match it, and FastAPI serialises it as a plain string.
    `admin_only` rides alongside, so the presentation layer can decide who is shown
    the precise text without any of those callers changing.
    """

    admin_only: bool

    def __new__(cls, reason: str, admin_only: bool = False) -> "SyncBlock":
        obj = super().__new__(cls, reason)
        obj.admin_only = admin_only
        return obj

    @property
    def reason(self) -> str:
        """The precise, admin-facing explanation."""
        return str(self)

    def message_for(self, is_admin: bool) -> str:
        """The text to SHOW this viewer. Admins always get the precise reason."""
        if self.admin_only and not is_admin:
            return ADMIN_FIX_NOTICE
        return str(self)


async def assessment_block_reason(
    db: AsyncSession,
    exam: CBTExam,
    org_id: str,
) -> "SyncBlock | None":
    """Why `exam`'s results can't reach StudentAssessmentScore, or None if they can.

    READ-ONLY, deliberately: this is what the CBT results panel and the Make Report
    notice call, and a status check must never create an Assessment as a side
    effect. `sync_cbt_to_assessment_score` calls it first and then re-resolves the
    term itself — two extra indexed SELECTs on a path that only runs when results
    are published, which is a fair price for a status helper that writes nothing.

    The counterpart to `_feed_block_reason` in the CBT router, which does this job
    for the gradebook feed. Unlike that one it must be async: the freeze check and
    the term lookups are queries, not attribute reads.

    Anything this returns is also returned by the sync, so the reason a teacher is
    shown and the reason the sync acted on cannot drift apart.
    """
    from app.models.modules.platform import AcademicTerm

    if not exam.subject_id:
        return SyncBlock("Exam has no subject assigned")
    if not exam.term:
        return SyncBlock("Exam has no term assigned")
    if not exam.results_published_at:
        return SyncBlock("Exam results not published yet")

    # A published class report is frozen, and this path would otherwise move the
    # marks behind it. It SKIPS rather than raising, deliberately: a re-published
    # CBT exam is a legitimate act, and failing it here would block releasing
    # results to students for a reason that has nothing to do with CBT. Same
    # contract the other guards use, and the same shape as the gradebook feed's
    # `_feed_block_reason` — report why the feed was withheld, never silently
    # skip, never block the student release.
    #
    # The CBT->Grade path needs no equivalent: those rows land as DRAFT and staff
    # release them separately, so the draft status already buffers parents.
    # StudentAssessmentScore has no draft state, so this is the only buffer.
    #
    # NOT admin_only: a teacher can't retract the report themselves, but the fact
    # that their class's report is already out is exactly the context they need,
    # and it names the page to ask about.
    if exam.class_id:
        from app.services.report_lock import find_published_block

        if await find_published_block(db, org_id, {exam.class_id}, {exam.term}):
            return SyncBlock(
                f"This class's {exam.term} report is published — scores are frozen. "
                f"Retract it to 'approved' in Report Workflow to accept new marks."
            )

    # From here down the exam is fine and the ORG's setup is what's missing, so
    # every remaining block is admin_only.
    term_row = (await db.execute(
        select(AcademicTerm).where(
            AcademicTerm.org_id == org_id,
            AcademicTerm.name == exam.term,
        )
    )).scalar_one_or_none()
    if not term_row:
        # Term is free text on CBTExam and matched by value, so this fires on a
        # plain spelling drift between the exam and Academic Terms. See
        # docs/future-features.md section 6.
        return SyncBlock(
            f"No academic term named '{exam.term}' exists, so there is nothing to "
            f"attach these scores to. Add it under Academic Terms, or correct the "
            f"term on the exam.",
            admin_only=True,
        )

    if not await _resolve_sub_term(db, org_id):
        return SyncBlock(
            "No sub-terms are defined for this school, so scores have nowhere to "
            "land. Add at least one (usually 'Full-Term') under Academic Settings.",
            admin_only=True,
        )
    return None


async def _resolve_sub_term(db: AsyncSession, org_id: str):
    """The sub-term CBT scores attach to. Most assessments use "Full-Term"; fall
    back to any sub-term so a school that named theirs differently still works."""
    from app.models.modules.platform import AcademicSubTerm

    row = (await db.execute(
        select(AcademicSubTerm).where(
            AcademicSubTerm.org_id == org_id,
            AcademicSubTerm.name.in_(["Full-Term", "Full Term"]),
        )
    )).scalar_one_or_none()
    if row:
        return row
    return (await db.execute(
        select(AcademicSubTerm).where(AcademicSubTerm.org_id == org_id)
    )).scalar_one_or_none()


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

    # One source of truth for "why not", shared with the CBT results panel and the
    # Make Report notice. Whatever they show, the sync acted on.
    block = await assessment_block_reason(db, exam, org_id)
    if block:
        return 0, block

    # Guards passed, so both of these resolve; re-read rather than threading them
    # out of the read-only helper.
    from app.models.modules.platform import AcademicTerm

    term_row = (await db.execute(
        select(AcademicTerm).where(
            AcademicTerm.org_id == org_id,
            AcademicTerm.name == exam.term,
        )
    )).scalar_one_or_none()
    sub_term_row = await _resolve_sub_term(db, org_id)

    # Get or create the Assessment for this exam's term. Only reachable with a
    # valid term and sub-term, so a failure here is a genuine write problem rather
    # than missing setup - but it is still nothing a teacher can act on.
    assessment_id = await get_or_create_cbt_assessment(
        db, org_id, term_row.id, sub_term_row.id
    )
    if not assessment_id:
        return 0, SyncBlock(
            "Could not create the CBT assessment for this term.", admin_only=True
        )

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
