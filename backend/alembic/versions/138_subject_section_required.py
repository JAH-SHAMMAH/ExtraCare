"""A subject must belong to a section

Revision ID: 138_subject_section_required
Revises: 137_subject_section_scope
Create Date: 2026-10-03

Migration 137 added `subjects.section_id` nullable, because the backfill, the
split of the two shared subjects, six renames and 56 new rows are a DATA
operation — `scripts/scope_subjects_to_sections.py`, with a backup, a manifest
and a --remove. That script has run. This closes the window.

WHY NOT NULL MATTERS HERE MORE THAN USUAL. The unique constraint added in 137,
`UNIQUE (org_id, section_id, name)`, DOES NOT BITE while section_id is NULL:
Postgres treats NULLs as distinct in a unique index, so any number of
identically-named subjects would pass. The rule that exists to stop a second
"Mathematics" appearing in one section only starts enforcing once this lands.
That is the same NULL-distinctness property migration 133 had to design around,
here working against us rather than for us.

A nullable scope also invites reads of the form "this section OR NULL", and
treating NULL as a wildcard is how cross-scope bleed gets reintroduced by a
later well-meaning filter — the reasoning migration 134 records for
`assessments.session_id`.

Verified against production immediately before writing: 79 subjects, 0 with a
NULL section, split 9 / 21 / 49 across Early Years, Primary and Secondary —
exactly Educare's own catalogue sizes. And no mark, enrolment or timetable row
sits on a subject from a different section than its pupil's class.

The guard below refuses rather than letting the ALTER fail on a constraint name
nobody can read.
"""
import sqlalchemy as sa
from alembic import op

revision = "138_subject_section_required"
down_revision = "137_subject_section_scope"
branch_labels = None
depends_on = None

TABLE = "subjects"


def upgrade() -> None:
    orphans = op.get_bind().execute(sa.text(
        f"SELECT count(*) FROM {TABLE} WHERE section_id IS NULL")).scalar()
    if orphans:
        raise RuntimeError(
            f"{orphans} subject(s) have no section. A subject cannot be filed "
            f"under a school without one, and the uniqueness rule added in 137 "
            f"does not constrain them while they are NULL. Run "
            f"scripts/scope_subjects_to_sections.py first."
        )
    op.alter_column(TABLE, "section_id", existing_type=sa.String(length=36),
                    nullable=False)


def downgrade() -> None:
    op.alter_column(TABLE, "section_id", existing_type=sa.String(length=36),
                    nullable=True)
