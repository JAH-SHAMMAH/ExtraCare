"""Backfill enrolment sessions, then require them

Revision ID: 140_enrolment_session_required
Revises: 139_enrolment_session_id
Create Date: 2026-10-08

Resolves `student_subject_enrollments.session_id` from `academic_year`, then
tightens it to NOT NULL and adds the uniqueness that keys on it.

~~~ WHY THE BACKFILL IS IN THE MIGRATION AND NOT A SCRIPT ~~~
The first draft of this arc put the backfill in
`scripts/backfill_enrolment_session.py`, to be run BETWEEN 139 and 140. That is
wrong for how this service deploys, and would have caused an outage.

`alembic upgrade head` is folded into the Render Start Command and joined to
uvicorn with `&&`, so it runs on EVERY BOOT — including every wake from the free
tier's idle spin-down — and a failing migration stops uvicorn from ever starting.
Pushing 139/140/141 with the backfill as a separate manual step would mean the
deploy applied 139, reached 140, found 4,140 NULLs, and refused. The service
would not boot, and the fix would require a hand-run script against a database
the app could no longer reach. "Fails closed" is the right behaviour for a schema
the app disagrees with; it is the wrong behaviour for work the migration could
simply have done itself.

So the backfill runs here, in the same transaction as the tightening. Either the
column is populated and constrained, or nothing changed.

IDEMPOTENT. `WHERE session_id IS NULL` means a re-run is a no-op — which matters
because the Start Command replays `upgrade head` on every boot, and because a
partially-applied migration must be safe to resume.

DIALECT-SAFE. Written as a correlated subquery rather than PostgreSQL's
`UPDATE ... FROM`, which SQLite does not accept — the test suite runs on SQLite,
and a migration that only works on one dialect is not proved by the suite.

THE PRE-CHECK IS KEPT, as a safety net rather than the mechanism. It now catches
only rows whose `academic_year` matches NO session for their org — genuinely
unresolvable data that a human must decide about. Those cannot be auto-mapped
without inventing a session, which would be worse than stopping. Production holds
4,140 rows, all "2025/2026", with a matching session row: 0 unresolvable.

WHY THE UNIQUE CONSTRAINT IS HERE AND NOT IN 139. Postgres treats NULLs as
distinct, so `UNIQUE (org_id, student_id, subject_id, session_id)` added while the
column was still NULL would have been satisfied by every row without constraining
anything — the trap recorded for 137 -> 138.

THE OLD CONSTRAINT STAYS. `uq_student_subject_enrollment` keys on `academic_year`,
which is still populated and still read by `plan_backfill_sync` — imported and
CALLED by migration 128, which freezes its signature. Both constraints hold at
once and agree, because one year string maps to exactly one session.

DOWNGRADE IS REAL. It drops the constraint and re-nullables the column, and
deliberately does NOT clear `session_id`: the values remain correct, so a
re-upgrade is a no-op rather than a second full backfill. 139's downgrade drops
the column outright, which is where the data actually goes.
"""
from alembic import op
import sqlalchemy as sa

revision = "140_enrolment_session_required"
down_revision = "139_enrolment_session_id"
branch_labels = None
depends_on = None

TABLE = "student_subject_enrollments"
UQ = "uq_student_subject_enrollment_session"

# Correlated subquery, not UPDATE...FROM: valid on both PostgreSQL and SQLite.
BACKFILL = sa.text(f"""
    UPDATE {TABLE}
       SET session_id = (
            SELECT s.id FROM academic_sessions s
             WHERE s.org_id = {TABLE}.org_id
               AND s.name   = {TABLE}.academic_year
            )
     WHERE session_id IS NULL
       AND EXISTS (
            SELECT 1 FROM academic_sessions s
             WHERE s.org_id = {TABLE}.org_id
               AND s.name   = {TABLE}.academic_year
            )
""")

UNRESOLVABLE = sa.text(f"""
    SELECT org_id, academic_year, count(*) AS n
      FROM {TABLE}
     WHERE session_id IS NULL
     GROUP BY org_id, academic_year
     ORDER BY n DESC
""")


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(BACKFILL)

    rows = conn.execute(UNRESOLVABLE).fetchall()
    if rows:
        detail = "; ".join(
            f"org {r[0]}: academic_year {r[1]!r} x{r[2]}" for r in rows)
        raise RuntimeError(
            "Enrolment rows carry an academic_year with no matching session for "
            f"their org, so session_id cannot be resolved — {detail}. Create the "
            "missing academic_sessions row (name must equal the academic_year "
            "string exactly), or correct the rows, then deploy again. Nothing "
            "has been changed by this migration."
        )

    op.alter_column(TABLE, "session_id",
                    existing_type=sa.String(length=36), nullable=False)
    op.create_unique_constraint(
        UQ, TABLE, ["org_id", "student_id", "subject_id", "session_id"])


def downgrade() -> None:
    op.drop_constraint(UQ, TABLE, type_="unique")
    op.alter_column(TABLE, "session_id",
                    existing_type=sa.String(length=36), nullable=True)
