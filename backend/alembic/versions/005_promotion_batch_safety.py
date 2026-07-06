"""Add promotion-run safety columns (batch_id, prev_is_active, reverted_at)

Revision ID: 005_promotion_batch_safety
Revises: 004_add_admissions_enrollment
Create Date: 2026-06-21 01:00:00.000000

Adds the columns that make a bulk promotion run previewable, audited, and
reversible:
- batch_id        groups every record from one run (revert by batch)
- prev_is_active  snapshot of the student's active flag before the run
- reverted_at     marks records undone by a revert

Additive + reversible. Existing rows get batch_id = their own id (each legacy
row becomes its own singleton batch) and prev_is_active = 1.
"""

from alembic import op
import sqlalchemy as sa


revision = "005_promotion_batch_safety"
down_revision = "004_add_admissions_enrollment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New columns are added nullable / server-default so existing rows are valid,
    # then batch_id is backfilled and tightened to NOT NULL where supported.
    op.add_column("promotion_records", sa.Column("batch_id", sa.String(36), nullable=True))
    op.add_column("promotion_records", sa.Column("prev_is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("promotion_records", sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True))

    # Backfill: each pre-existing record becomes its own singleton batch.
    op.execute("UPDATE promotion_records SET batch_id = id WHERE batch_id IS NULL")

    op.create_index("ix_promotion_records_batch_id", "promotion_records", ["batch_id"])
    op.create_index("ix_promotion_records_batch", "promotion_records", ["batch_id", "org_id"])

    # SQLite can't ALTER a column to NOT NULL in place; the app/model treats it
    # as required and the backfill guarantees no NULLs. On Postgres/MySQL we
    # tighten the constraint.
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("promotion_records", "batch_id", existing_type=sa.String(36), nullable=False)


def downgrade() -> None:
    op.drop_index("ix_promotion_records_batch", table_name="promotion_records")
    op.drop_index("ix_promotion_records_batch_id", table_name="promotion_records")
    op.drop_column("promotion_records", "reverted_at")
    op.drop_column("promotion_records", "prev_is_active")
    op.drop_column("promotion_records", "batch_id")
