"""At most one current session per org

Revision ID: 141_one_current_session
Revises: 140_enrolment_session_required
Create Date: 2026-10-08

`academic_sessions.is_current` decides which session the gate on marks resolves.
Exclusivity is enforced only in application code — two router paths run
`UPDATE academic_sessions SET is_current = FALSE` across the org before setting
one (`platform.py` ~283 and ~302). Nothing stops a script, a direct INSERT or an
importer from leaving two rows current, and the Educare import creates sessions
in bulk, which is precisely the thing that would.

Two current sessions is not a cosmetic fault: `resolve_academic_year` picks the
current session, so a second one makes which session a mark belongs to depend on
row order.

A PARTIAL UNIQUE INDEX, NOT A UNIQUE CONSTRAINT. The rule is "at most one row per
org WHERE is_current" — a plain UNIQUE (org_id, is_current) would also forbid a
second NON-current session, i.e. forbid having any history at all.

~~~ THE DIALECT TRAP THIS MIGRATION IS MOST LIKELY TO TRIP ~~~
`postgresql_where` is SILENTLY IGNORED on SQLite. Without `sqlite_where` as well,
the partial index degrades to a FULL unique on (org_id) under the test suite —
which would forbid an org from having more than ONE session row at all, and break
every multi-session test in a way that looks nothing like its cause. This is the
drift recorded for migration 133; both dialect clauses are passed deliberately.

PRE-CHECK BEFORE CREATING IT. Creating a unique index on data that already
violates it fails partway through. The check below names the offending orgs
instead, so the fix is a data decision made with the facts rather than an opaque
IntegrityError during a deploy. Production at the time of writing holds two
sessions, exactly one current.
"""
from alembic import op
import sqlalchemy as sa

revision = "141_one_current_session"
down_revision = "140_enrolment_session_required"
branch_labels = None
depends_on = None

TABLE = "academic_sessions"
IX = "uq_one_current_session_per_org"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        f"SELECT org_id, count(*) AS n FROM {TABLE} "
        "WHERE is_current GROUP BY org_id HAVING count(*) > 1"
    )).fetchall()
    if rows:
        detail = ", ".join(f"org {r[0]}: {r[1]} current" for r in rows)
        raise RuntimeError(
            "Cannot add the one-current-session index while these orgs have more "
            f"than one current session — {detail}. Decide which session is "
            "current for each, unset the others, then re-run this migration."
        )

    op.create_index(
        IX, TABLE, ["org_id"], unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index(IX, table_name=TABLE)
