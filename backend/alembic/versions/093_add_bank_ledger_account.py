"""Finance: link a bank account to its cash ledger account (Broad View balances)

Revision ID: 093_bank_ledger_account
Revises: 092_timetable_curriculum
Create Date: 2026-07-23 09:00:00.000000

Additive + reversible. Adds bank_accounts.ledger_account_id so each bank's CURRENT
balance can be derived from its cash ledger account (Broad View → Bank Account
Statements).
"""
from alembic import op
import sqlalchemy as sa


revision = "093_bank_ledger_account"
down_revision = "092_timetable_curriculum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain column add (dialect-safe). The ORM model declares the ForeignKey for
    # relationship semantics; a DB-level constraint isn't required for this
    # optional read-only reference and SQLite can't ALTER-ADD one.
    op.add_column("bank_accounts", sa.Column("ledger_account_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("bank_accounts", "ledger_account_id")
