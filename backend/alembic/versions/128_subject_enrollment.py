"""StudentSubjectEnrollment: the register of who takes what, + backfill from marks

Revision ID: 128_subject_enrollment
Revises: 127_subject_report_comment
Create Date: 2026-09-26

Two parts, and the order matters:

1. Creates `student_subject_enrollments`.

2. **Backfills a row for every (pupil, subject) pair that ALREADY has a mark**,
   from the UNION of `student_assessment_scores` and `grades`.

(2) is not cosmetic — without it the gate breaks every existing mark. Enrolment
becomes a precondition for entering a mark, so on the day this ships a teacher
reopening any of the ~1,800 marks already in the system and re-saving it would be
refused. An existing mark is itself the evidence that the pupil takes the subject.

WHY THE UNION. The two stores disagreed at Fairview: 1,799 pairs in
`student_assessment_scores`, 1,800 in `grades`. The single pair only in `grades`
was a real pupil — FSN-0031 Musa Yusuf, Biology — whose assessment-score row was
lost when a CBT re-sync dropped mid-run. Backfilling from the new store alone
would have left him unenrolled in a subject he has a grade for, which would not
have surfaced until someone questioned that report card.

Scope is derived from the data, never hardcoded: exactly the pairs that have
marks, only those not already enrolled, and per organisation. Idempotent — a
second run creates nothing.

The academic year comes from the org's current session (falling back to its only
session). An org with no resolvable session is SKIPPED rather than guessed at:
enrolments split across two different year strings would make the gate refuse
marks for reasons nobody could see.

The planner lives in app/services/subject_enrollment.py so the dry-run script
executes the same code path this migration does. That module's `plan_backfill`
and `resolve_academic_year` are FROZEN for this migration's sake: change what
they select and you change what an already-shipped migration would do on a fresh
database. New behaviour belongs in a new module and a new revision.
"""
import sqlalchemy as sa
from alembic import op

revision = "128_subject_enrollment"
down_revision = "127_subject_report_comment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_subject_enrollments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("student_id", sa.String(length=36),
                  sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(length=36),
                  sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("enrolled_by", sa.String(length=36),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("org_id", "student_id", "subject_id", "academic_year",
                            name="uq_student_subject_enrollment"),
    )
    op.create_index("ix_student_subject_enrollments_student_id",
                    "student_subject_enrollments", ["student_id"])
    op.create_index("ix_student_subject_enrollments_subject_id",
                    "student_subject_enrollments", ["subject_id"])
    op.create_index("ix_student_subject_enrollments_academic_year",
                    "student_subject_enrollments", ["academic_year"])
    op.create_index("ix_student_subject_enrollments_year",
                    "student_subject_enrollments", ["org_id", "academic_year"])
    op.create_index("ix_student_subject_enrollments_lookup",
                    "student_subject_enrollments",
                    ["org_id", "student_id", "subject_id", "academic_year"])

    _backfill()


def _backfill() -> None:
    """Enrol every (pupil, subject) pair that already has a mark.

    Delegates to app/services/subject_enrollment so the dry-run script previews
    THIS code rather than a copy of it — the same arrangement migration 125 uses
    with report_approval_backfill. A second copy of the SELECT here would drift,
    and the preview would then stop describing what this migration does.
    """
    from app.services.subject_enrollment import (
        apply_backfill_sync, current_year_by_org, plan_backfill_sync,
    )

    # `alembic upgrade --sql` emits statements without running them, so a read
    # returns None. This backfill is DATA-DERIVED — one row per existing mark — so
    # it cannot be rendered as static SQL at all, unlike the CREATE TABLE above.
    # Skipping it offline keeps the table's DDL reviewable without a database,
    # which is how this project checks a migration before it reaches production.
    # Online behaviour is unchanged.
    if op.get_context().as_sql:
        print("[128] offline render — data-derived backfill skipped (see docstring)")
        return

    conn = op.get_bind()
    years = current_year_by_org(conn)          # orgs with no resolvable session are absent
    total = 0
    for org_id, year in years.items():
        pairs = plan_backfill_sync(conn, org_id=org_id, academic_year=year)
        total += apply_backfill_sync(conn, org_id=org_id, academic_year=year, pairs=pairs)

    print(f"[128] backfilled {total} subject enrolment(s) from existing marks")


def downgrade() -> None:
    op.drop_index("ix_student_subject_enrollments_lookup", table_name="student_subject_enrollments")
    op.drop_index("ix_student_subject_enrollments_year", table_name="student_subject_enrollments")
    op.drop_index("ix_student_subject_enrollments_academic_year", table_name="student_subject_enrollments")
    op.drop_index("ix_student_subject_enrollments_subject_id", table_name="student_subject_enrollments")
    op.drop_index("ix_student_subject_enrollments_student_id", table_name="student_subject_enrollments")
    op.drop_table("student_subject_enrollments")
