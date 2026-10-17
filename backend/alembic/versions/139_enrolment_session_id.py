"""Enrolment points at a session row, not a year string

Revision ID: 139_enrolment_session_id
Revises: 138_subject_section_required
Create Date: 2026-10-08

`student_subject_enrollments.academic_year` is the string "2025/2026" on all
4,140 rows. The gate on marks resolves the current session's NAME and matches it
against that string, so enrolment is keyed on text that nothing guarantees stays
in step with `academic_sessions`. This is the same shape as the column behind the
2026-09-27 outage, where `report_approvals.term` said 'Term 1' while the terms
were Autumn/Spring/Summer and every parent was told their child's report was
unpublished. Migration 131 fixed that one by making it a real FK; this is the
same fix for enrolment, before three sessions of imported history multiply it.

THE MODEL DOCSTRING ARGUES AGAINST THIS, AND IT IS NOW OUT OF DATE. It says
keying on `academic_sessions.id` would "silently bind every enrolment to Autumn",
because that table's single row carried BOTH `name='2025/2026'` AND
`term='Autumn'` — a session/term hybrid. That was true when it was written. It is
not true now:

  * `academic_sessions` holds one row PER YEAR — 2025/2026 and 2026/2027 today,
    not three rows a year.
  * `term` on that table is nullable, legacy free text (2026/2027 has NULL).
    The structured term list is `academic_terms`, whose own docstring calls
    `AcademicSession.term` "free-text" and itself "the structured report-domain
    list".
  * Migration 134 already treats `session_id` on `assessments` as the YEAR, and
    `term_periods` keys (session, term, sub_term) as three separate columns.

So a session id denotes a year, and binding enrolment to one does not bind it to
a term. The model docstring is corrected in the same change as this migration.

NULLABLE HERE ON PURPOSE. The backfill is a DATA operation
(`scripts/backfill_enrolment_session.py`, dry-run by default, manifest, --remove)
and migration 140 tightens this to NOT NULL once that has run and verified zero
nulls. The 137 -> 138 pattern, for the same reason: a uniqueness or NOT NULL rule
added while the column is still NULL does not bite, because Postgres treats NULLs
as distinct.

THE NEW UNIQUE CONSTRAINT IS DELIBERATELY NOT ADDED HERE. It belongs in 140,
after the column is NOT NULL — added now it would be satisfied by every row
simply because every row is NULL.

RESTRICT, NOT CASCADE, matching migration 134's reasoning exactly: `term_id`
cascades and `student_assessment_scores.assessment_id` cascades in turn, so a
cascading session FK would put a whole year of enrolment one DELETE away.
Deleting a session that still has enrolment has to be refused, not absorbed.

`academic_year` IS NOT DROPPED, here or in 140. `plan_backfill_sync` in
`app/services/subject_enrollment.py` is imported and CALLED by migration 128 at
line 110, which freezes its signature — it filters on `academic_year`, and the
column has to outlive it. The drop is a separate, later migration, held until
after the Educare import is stable.
"""
from alembic import op
import sqlalchemy as sa

revision = "139_enrolment_session_id"
down_revision = "138_subject_section_required"
branch_labels = None
depends_on = None

TABLE = "student_subject_enrollments"
FK = f"fk_{TABLE}_session"
IX = f"ix_{TABLE}_org_session"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("session_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        FK, TABLE, "academic_sessions", ["session_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(IX, TABLE, ["org_id", "session_id"])


def downgrade() -> None:
    op.drop_index(IX, table_name=TABLE)
    op.drop_constraint(FK, TABLE, type_="foreignkey")
    op.drop_column(TABLE, "session_id")
