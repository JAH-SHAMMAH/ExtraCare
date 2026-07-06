"""Add salary_advances + salary_advance_repayments (Finance: Salary Advance)

Revision ID: 016_add_salary_advance
Revises: 015_add_hr_extended
Create Date: 2026-06-23 19:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "016_add_salary_advance"
down_revision = "015_add_hr_extended"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "salary_advances", *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staff_user_id", sa.String(36), nullable=False),
        sa.Column("staff_name", sa.String(200), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("amount_repaid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disburse_entry_id", sa.String(36), nullable=True),
        sa.Column("advance_account_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_salary_advances"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE", name="fk_salary_advances_staff_user_id_users"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL", name="fk_salary_advances_requested_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_salary_advances_approved_by_users"),
        sa.ForeignKeyConstraint(["disburse_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_salary_advances_disburse_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["advance_account_id"], ["ledger_accounts.id"], ondelete="SET NULL", name="fk_salary_advances_advance_account_id_ledger_accounts"),
        sa.CheckConstraint("amount > 0", name="ck_salary_advances_amount_pos"),
    )
    op.create_index("ix_salary_advances_id", "salary_advances", ["id"])
    op.create_index("ix_salary_advances_org_id", "salary_advances", ["org_id"])
    op.create_index("ix_salary_advances_staff_user_id", "salary_advances", ["staff_user_id"])
    op.create_index("ix_salary_advances_org_status", "salary_advances", ["org_id", "status"])

    op.create_table(
        "salary_advance_repayments", *_base(),
        sa.Column("advance_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="payroll"),
        sa.Column("payroll_run_id", sa.String(36), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_salary_advance_repayments"),
        sa.ForeignKeyConstraint(["advance_id"], ["salary_advances.id"], ondelete="CASCADE", name="fk_sa_repay_advance_id_salary_advances"),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_runs.id"], ondelete="SET NULL", name="fk_sa_repay_payroll_run_id_payroll_runs"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_sa_repay_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_sa_repay_recorded_by_users"),
        sa.CheckConstraint("amount > 0", name="ck_salary_advance_repay_amount_pos"),
    )
    op.create_index("ix_salary_advance_repayments_id", "salary_advance_repayments", ["id"])
    op.create_index("ix_salary_advance_repayments_org_id", "salary_advance_repayments", ["org_id"])
    op.create_index("ix_salary_advance_repayments_advance_id", "salary_advance_repayments", ["advance_id"])
    op.create_index("ix_salary_advance_repay_advance", "salary_advance_repayments", ["advance_id", "org_id"])


def downgrade() -> None:
    op.drop_table("salary_advance_repayments")
    op.drop_table("salary_advances")
