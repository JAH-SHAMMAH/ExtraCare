"""StudentAssessmentScore.source — make a mark's provenance answerable

Revision ID: 129_score_provenance
Revises: 128_subject_enrollment
Create Date: 2026-09-27

THE GAP THIS CLOSES. Every one of the 1,799 marks in production had
`recorded_by = NULL`, so no mark on any report card was traceable to anyone. The
cause was not the column but the CBT sync, which wrote scores without ever
stamping an author. The two human paths (the Report Entry grid, Reports Upload)
always did.

`recorded_by` alone cannot close it, because a NULL there is ambiguous: it could
mean a machine wrote the mark, or that a human author was lost. `source` makes
the distinction explicit —

    entry     the Report Entry grid, by a named teacher
    upload    Reports Upload, by a named person
    cbt_sync  the automated CBT feed; recorded_by is set when a person triggered
              it (publishing results / manual re-sync) and NULL for a script run

BACKFILL. Existing rows are labelled from the data, never assumed: a row with no
author against an assessment whose code is 'CBT' can only have come from the
sync, since both human paths stamp an author. Those become source='cbt_sync' with
recorded_by left NULL — which is the truth. No author is invented for them,
because none exists to name; what changes is that their authorlessness is now a
recorded fact rather than a silence.

Rows that already carry an author are left alone: they were written by a human
path, and which of the two is not recoverable after the fact. Their source stays
NULL rather than being guessed at.

Idempotent — a second run matches nothing new.
"""
import sqlalchemy as sa
from alembic import op

revision = "129_score_provenance"
down_revision = "128_subject_enrollment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_assessment_scores",
                  sa.Column("source", sa.String(length=20), nullable=True))

    conn = op.get_bind()
    # Authorless + a CBT assessment => the sync wrote it. Derived from the data:
    # the assessment's CODE is matched, not a hardcoded id or name.
    res = conn.execute(sa.text("""
        UPDATE student_assessment_scores s
           SET source = 'cbt_sync'
         WHERE s.source IS NULL
           AND s.recorded_by IS NULL
           AND EXISTS (SELECT 1 FROM assessments a
                        WHERE a.id = s.assessment_id AND upper(a.code) = 'CBT')
    """))

    # `alembic upgrade --sql` emits statements without running them, so execute()
    # returns None there and any attempt to READ a result is an AttributeError.
    # Offline rendering is how this project inspects a migration's DDL before it
    # touches production, so it has to keep working: the counts below are progress
    # reporting, not part of the migration, and are skipped when there is nothing
    # to count.
    if op.get_context().as_sql:
        return

    print(f"[129] labelled {res.rowcount} authorless CBT score(s) as source='cbt_sync'")

    # Anything still unlabelled is reported, not guessed at — so a real gap stays
    # visible instead of being papered over with a plausible-looking value.
    left = conn.execute(sa.text(
        "SELECT count(*) FROM student_assessment_scores WHERE source IS NULL")).scalar()
    if left:
        print(f"[129] {left} score(s) left with source NULL — they carry an author, "
              f"or came from an assessment that is not CBT")


def downgrade() -> None:
    op.drop_column("student_assessment_scores", "source")
