"""Session-scope the report setup: assessments and cumulatives belong to a year

Revision ID: 134_session_scoped_setup
Revises: 133_non_assessment_comment
Create Date: 2026-09-30

THE PROBLEM. Terms are ORG-WIDE and shared across sessions: "Autumn" is one row
in `academic_terms`, reused every year. Assessments and cumulatives were scoped
to (term, sub-term) and nothing else, so the moment a school starts 2026/2027 its
Autumn marks would be entered against the SAME assessment rows that hold
2025/2026's, and no query afterwards could tell the two years apart. The damage
is silent and cumulative — exactly the failure mode of the `report_approvals.term`
and `cbt_exams.term` name-matching this branch removed in 131 and 132.

BOTH TABLES, not just assessments. An empty `cumulatives` set is what made every
subject on every card grade F earlier in this work; a new session that inherited
last year's assessments but found no cumulative of its own would reproduce that
bug precisely. So the year has to be carried by both halves of the setup.

SCORES GET NOTHING. `student_assessment_scores` reaches its session through
`assessment_id`, so it needs no column — and its existing unique constraint
(org, student, subject, assessment) keeps working untouched, because a new
session means new assessment ROWS: next year's mark for the same pupil and
subject is a different key, not a conflict. `cumulative_components` likewise
inherits through `cumulative_id`.

WHY RESTRICT AND NOT CASCADE. `assessments.term_id` is ON DELETE CASCADE, and
`student_assessment_scores.assessment_id` is ON DELETE CASCADE in turn (both
verified against production before writing this). A cascading session FK would
therefore chain DELETE session -> assessments -> marks, putting a whole academic
year one request away; `DELETE /platform/sessions/{id}` exists and had no
dependency guard at all. RESTRICT makes the database refuse, and the endpoint
now returns a 409 that names the counts instead of relying on that refusal to
surface as an opaque 500.

THE BACKFILL IS UNAMBIGUOUS. Verified against production immediately before
writing: one organisation, one session ('2025/2026', is_current), 4 assessments
and 5 cumulatives, every one of which previewed to that session. Zero rows belong
to an org with no session, which is the only thing that could block the NOT NULL.
The pick order below (current first, then latest start, then oldest created)
mirrors `subject_enrollment.resolve_academic_year`, so the column agrees with the
session string enrolment has been keyed on since migration 128.

NOT NULL rather than nullable. A nullable session_id invites reads of the form
"this session OR NULL", and treating NULL as a wildcard is how cross-year bleed
gets reintroduced by a later well-meaning filter. A missing session now fails
loudly at INSERT instead.
"""
import sqlalchemy as sa
from alembic import op

revision = "134_session_scoped_setup"
down_revision = "133_non_assessment_comment"
branch_labels = None
depends_on = None

TABLES = ("assessments", "cumulatives")

# Current session first; then the latest-starting; then the oldest row, so the
# choice is deterministic even for an org that never set the flag.
BACKFILL = """
    UPDATE {table} AS t
       SET session_id = (
             SELECT s.id FROM academic_sessions s
              WHERE s.org_id = t.org_id
              ORDER BY s.is_current DESC, s.start_date DESC NULLS LAST, s.created_at
              LIMIT 1)
     WHERE t.session_id IS NULL
"""


def upgrade() -> None:
    for table in TABLES:
        # Added nullable so the backfill has something to write into; tightened
        # to NOT NULL once every row carries a year.
        op.add_column(table, sa.Column("session_id", sa.String(length=36), nullable=True))
        op.execute(sa.text(BACKFILL.format(table=table)))

        orphans = op.get_bind().execute(sa.text(
            f"SELECT count(*) FROM {table} WHERE session_id IS NULL")).scalar()
        if orphans:
            # Refused rather than papered over: the alter below would fail anyway,
            # and this says which table and how many instead of a constraint name.
            raise RuntimeError(
                f"{orphans} row(s) in {table} belong to an organisation with no "
                f"academic session, so they cannot be assigned a year. Create a "
                f"session for that organisation and re-run."
            )

        op.alter_column(table, "session_id", existing_type=sa.String(length=36),
                        nullable=False)
        op.create_foreign_key(
            f"fk_{table}_session", table, "academic_sessions",
            ["session_id"], ["id"], ondelete="RESTRICT",
        )
        op.create_index(f"ix_{table}_org_session_term", table,
                        ["org_id", "session_id", "term_id"])
        op.create_index(f"ix_{table}_session_id", table, ["session_id"])


def downgrade() -> None:
    # Dropping the column merges every session's setup back into one namespace.
    # Non-destructive only while a single session exists — which is the state this
    # migration was written against, and is asserted rather than assumed.
    sessions = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM academic_sessions")).scalar()
    if sessions and sessions > 1:
        raise RuntimeError(
            f"{sessions} academic sessions exist. Dropping session_id would merge "
            f"their assessments and cumulatives into one indistinguishable set, "
            f"silently mixing years of marks. Remove the extra sessions' setup "
            f"rows first if this downgrade is really intended."
        )
    for table in TABLES:
        op.drop_index(f"ix_{table}_session_id", table_name=table)
        op.drop_index(f"ix_{table}_org_session_term", table_name=table)
        op.drop_constraint(f"fk_{table}_session", table, type_="foreignkey")
        op.drop_column(table, "session_id")
