"""StudentReport.term -> term_id + session_id: the last name-keyed report table

Revision ID: 135_student_report_term_id
Revises: 134_session_scoped_setup
Create Date: 2026-10-01

`student_reports` stores the term as a NAME. It holds the only human-authored
content on a report card that is not a mark — the class-teacher and head-teacher
comments, and the attendance summary — and `report_card` finds the row by
comparing that string to the term being rendered. Rename a term in Report Setup
and the comparison silently matches nothing: every card loses its comments and
attendance, with no error anywhere. That is the fourth table with this defect,
after `report_approvals` (131), `cbt_exams` (132) and the report setup (134).

BOTH COLUMNS, NOT JUST term_id. Terms are ORG-WIDE and shared across sessions —
"Autumn" is one row reused every year, which is migration 134's whole premise.
Swapping the constraint to (student_id, term_id, org_id) alone would permit
exactly ONE report per pupil per term FOREVER: 2026/2027 Autumn would collide
with 2025/2026 Autumn. That is the defect 134 removed, reintroduced in a new
table. So the uniqueness key gains the session as well.

`academic_year` GOES TOO. It is NULL on all 180 rows, so nothing is lost, and
keeping a free-text year string beside `session_id` would leave two sources for
"which year" on one row — the exact drift this migration exists to remove.
`get_report_card` resolves the display year from the session instead.

FK CHOICES, matching the established pattern:
  term_id    CASCADE  — as `report_approvals.term_id` (131). The term-delete
                        guard warns with counts and then destroys on confirm, and
                        CASCADE keeps that design working. The guard is updated in
                        the same change to move student reports out of its
                        "stranded by name" bucket and into the HARD bucket, since
                        a confirmed delete now destroys authored comments rather
                        than merely orphaning them. Understating that would be
                        worse than the silent stranding it replaces.
  session_id RESTRICT  — as migration 134. A session must not be deletable out
                        from under a year of reports.

VERIFIED AGAINST PRODUCTION before writing: 180 rows, every one carrying
term='Autumn', which resolves to a real academic_terms row (0 unresolvable);
academic_year NULL on all of them, so the session comes from the same preference
order 134 and `resolve_academic_year` use; and 0 duplicate groups under the new
key, so the constraint applies without a dedupe pass.
"""
import sqlalchemy as sa
from alembic import op

revision = "135_student_report_term_id"
down_revision = "134_session_scoped_setup"
branch_labels = None
depends_on = None

TABLE = "student_reports"
OLD_UQ = "uq_student_report_student_term"
NEW_UQ = "uq_student_report_student_session_term"

# Name -> id against the authoritative table. This is NOT the string comparison
# being removed: that one compared two tables' copies of a name and matched
# nothing when they drifted. This resolves against `academic_terms` itself, once,
# and anything it cannot resolve is reported rather than silently skipped.
BACKFILL_TERM = f"""
    UPDATE {TABLE} AS sr
       SET term_id = (SELECT t.id FROM academic_terms t
                       WHERE t.name = sr.term AND t.org_id = sr.org_id
                       LIMIT 1)
     WHERE sr.term_id IS NULL
"""

# Current session first, then the latest-starting, then the oldest — identical to
# migration 134, so the two columns cannot disagree about which year it is.
BACKFILL_SESSION = f"""
    UPDATE {TABLE} AS sr
       SET session_id = (SELECT s.id FROM academic_sessions s
                          WHERE s.org_id = sr.org_id
                          ORDER BY s.is_current DESC,
                                   s.start_date DESC NULLS LAST,
                                   s.created_at
                          LIMIT 1)
     WHERE sr.session_id IS NULL
"""


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("term_id", sa.String(length=36), nullable=True))
    op.add_column(TABLE, sa.Column("session_id", sa.String(length=36), nullable=True))

    op.execute(sa.text(BACKFILL_TERM))
    op.execute(sa.text(BACKFILL_SESSION))

    bind = op.get_bind()
    for col, what in (("term_id", "a term"), ("session_id", "an academic session")):
        orphans = bind.execute(sa.text(
            f"SELECT count(*) FROM {TABLE} WHERE {col} IS NULL")).scalar()
        if orphans:
            # Refused rather than papered over. The ALTER below would fail anyway;
            # this says which column and how many instead of a constraint name.
            raise RuntimeError(
                f"{orphans} row(s) in {TABLE} could not be matched to {what}. "
                f"A report whose term name no longer exists cannot be migrated "
                f"without deciding which term it meant, and guessing would attach "
                f"authored comments to the wrong term."
            )

    op.alter_column(TABLE, "term_id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column(TABLE, "session_id", existing_type=sa.String(length=36), nullable=False)

    op.create_foreign_key(f"fk_{TABLE}_term", TABLE, "academic_terms",
                          ["term_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(f"fk_{TABLE}_session", TABLE, "academic_sessions",
                          ["session_id"], ["id"], ondelete="RESTRICT")

    # The old key could not tell two sessions apart; this one can.
    op.drop_constraint(OLD_UQ, TABLE, type_="unique")
    op.create_unique_constraint(
        NEW_UQ, TABLE, ["org_id", "student_id", "session_id", "term_id"])

    op.create_index(f"ix_{TABLE}_org_session_term", TABLE,
                    ["org_id", "session_id", "term_id"])

    # Both name columns go: the whole point is that there is one source of truth.
    op.drop_index("ix_student_reports_org_term", table_name=TABLE)
    op.drop_column(TABLE, "term")
    op.drop_column(TABLE, "academic_year")


def downgrade() -> None:
    op.add_column(TABLE, sa.Column("term", sa.String(length=50), nullable=True))
    op.add_column(TABLE, sa.Column("academic_year", sa.String(length=20), nullable=True))

    # Names restored from the ids, so a downgrade is not lossy for `term`.
    op.execute(sa.text(f"""
        UPDATE {TABLE} AS sr
           SET term = (SELECT t.name FROM academic_terms t WHERE t.id = sr.term_id),
               academic_year = (SELECT s.name FROM academic_sessions s
                                 WHERE s.id = sr.session_id)
    """))

    # A pupil may now hold the same term in two sessions, which the old key
    # cannot express. Asserted rather than silently collapsing two years of
    # authored comments into one row.
    dupes = op.get_bind().execute(sa.text(f"""
        SELECT count(*) FROM (
          SELECT student_id, term, org_id FROM {TABLE}
           GROUP BY 1,2,3 HAVING count(*) > 1) x""")).scalar()
    if dupes:
        raise RuntimeError(
            f"{dupes} (student, term) group(s) exist in more than one session. The "
            f"pre-135 constraint cannot represent that, and collapsing them would "
            f"destroy one year's comments. Remove the extra sessions' reports "
            f"first if this downgrade is really intended."
        )

    op.alter_column(TABLE, "term", existing_type=sa.String(length=50), nullable=False)
    op.create_index("ix_student_reports_org_term", TABLE, ["org_id", "term"])
    op.drop_index(f"ix_{TABLE}_org_session_term", table_name=TABLE)
    op.drop_constraint(NEW_UQ, TABLE, type_="unique")
    op.create_unique_constraint(OLD_UQ, TABLE, ["student_id", "term", "org_id"])
    op.drop_constraint(f"fk_{TABLE}_session", TABLE, type_="foreignkey")
    op.drop_constraint(f"fk_{TABLE}_term", TABLE, type_="foreignkey")
    op.drop_column(TABLE, "session_id")
    op.drop_column(TABLE, "term_id")
