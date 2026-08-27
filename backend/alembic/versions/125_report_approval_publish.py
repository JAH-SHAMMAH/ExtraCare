"""ReportApproval: publish stamps + backfill rows for grades already published

Revision ID: 125_report_approval_publish
Revises: 124_admin_coord_settings
Create Date: 2026-08-26

Two things, and the order matters:

1. Adds `published_by` / `published_at` to report_approvals — the audit stamp for
   the stage that actually releases a class's cards to parents.

2. Backfills a `published` report_approvals row for every (org, class, term) that
   ALREADY has published grades.

(2) is not cosmetic. The parent report card now requires a `published` workflow
row on top of the existing Grade.status filter. Every card visible to a parent
today was published before that workflow was mandatory, so it has no row behind
it — without this backfill the gate would blank ~1800 live grades across 12
classes the moment it ships. The backfill re-states the status quo in the
vocabulary the new gate reads.

Scope is derived from the data, never hardcoded: exactly the (class, term) pairs
that have published grades, and only those without a row already. Idempotent —
a second run creates nothing.

The planner lives in app/services/report_approval_backfill.py so the dry-run
script executes the same code path this migration does. That module is FROZEN
for this migration's sake: change what the backfill selects and you change what
an already-shipped migration would do on a fresh database. New behaviour belongs
in a new module and a new revision.
"""
from alembic import op
import sqlalchemy as sa

from app.services.report_approval_backfill import (
    BACKFILL_NOTE, apply_backfill, plan_backfill,
)


revision = "125_report_approval_publish"
down_revision = "124_admin_coord_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("report_approvals", sa.Column("published_by", sa.String(36), nullable=True))
    op.add_column("report_approvals", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    # Named constraint, added separately — the convention the other migrations in
    # this tree follow (see 120). Skipped on SQLite, which cannot ALTER a
    # constraint into an existing table; production is Postgres, and skipping
    # keeps the migration runnable against a SQLite copy for verification.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_report_approvals_published_by", "report_approvals", "users",
            ["published_by"], ["id"], ondelete="SET NULL",
        )
    conn = op.get_bind()
    to_create, skipped = plan_backfill(conn)
    written = apply_backfill(conn, to_create)

    # Printed into the deploy log: on production this is the only record of what
    # the backfill touched, and "0 written" needs to be distinguishable from
    # "never ran".
    print(f"[125] report_approvals backfill: {written} published row(s) created, "
          f"{len(skipped)} pair(s) left alone (row already present).")
    for row in to_create:
        print(f"[125]   + {row['class_name']} / {row['term']} "
              f"({row['grade_rows']} grades, {row['students']} students)")
    for row in skipped:
        print(f"[125]   = {row['class_name']} / {row['term']} "
              f"kept at stage '{row['existing_stage']}'")

    # One workflow row per class + term, added AFTER the backfill so the rows it
    # writes are already in place. Both gates resolve a class's stage by
    # (class, term), so a duplicate would make "the stage" ambiguous — a stale
    # second row could keep releasing a card the first one retracted.
    dupes = conn.execute(sa.text(
        "SELECT class_id, term, COUNT(*) FROM report_approvals "
        "WHERE class_id IS NOT NULL GROUP BY class_id, term HAVING COUNT(*) > 1"
    )).fetchall()
    if dupes:
        # Refuse rather than let the constraint fail with an opaque IntegrityError:
        # the operator needs to know WHICH rows to reconcile.
        listing = ", ".join(f"class={d[0]} term={d[1]!r} x{d[2]}" for d in dupes)
        raise RuntimeError(
            "[125] cannot add uq_report_approval_class_term — duplicate "
            f"(class, term) workflow rows already exist: {listing}. "
            "Reconcile them to one row each, then re-run this migration."
        )
    # Same SQLite carve-out as the FK above: the constraint is part of the model,
    # so a create_all-built test database has it natively.
    if conn.dialect.name != "sqlite":
        op.create_unique_constraint(
            "uq_report_approval_class_term", "report_approvals", ["class_id", "term"],
        )


def downgrade() -> None:
    # Only rows this migration wrote — matched on the marker note AND the stage it
    # set. A row an operator has since edited or moved off `published` is left
    # alone rather than silently deleted.
    op.get_bind().execute(
        sa.text("DELETE FROM report_approvals WHERE stage = 'published' AND notes = :note"),
        {"note": BACKFILL_NOTE},
    )
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("uq_report_approval_class_term", "report_approvals", type_="unique")
        op.drop_constraint("fk_report_approvals_published_by", "report_approvals", type_="foreignkey")
    op.drop_column("report_approvals", "published_at")
    op.drop_column("report_approvals", "published_by")
