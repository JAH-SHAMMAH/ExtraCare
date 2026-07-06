"""Add student wallets + cooperative (Batch 6 money features)

Revision ID: 010_add_wallet_cooperative
Revises: 009_add_finance_ops
Create Date: 2026-06-21 06:00:00.000000

Additive + reversible. Subledgers for ledger-backed student wallets / pocket
money and the cooperative. Balances are derived (no stored balance columns); the
liability control accounts live in the existing ledger_accounts table.
"""

from alembic import op
import sqlalchemy as sa


revision = "010_add_wallet_cooperative"
down_revision = "009_add_finance_ops"
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
        "student_wallets",
        *_base(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("spend_limit_daily", sa.Numeric(14, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_student_wallets"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_student_wallets_student_id_students"),
        sa.UniqueConstraint("org_id", "student_id", name="uq_student_wallets_org_student"),
    )
    op.create_index("ix_student_wallets_id", "student_wallets", ["id"])
    op.create_index("ix_student_wallets_org_id", "student_wallets", ["org_id"])
    op.create_index("ix_student_wallets_student_id", "student_wallets", ["student_id"])
    op.create_index("ix_student_wallets_student_org", "student_wallets", ["student_id", "org_id"])

    op.create_table(
        "wallet_entries",
        *_base(),
        sa.Column("wallet_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("signed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_entries"),
        sa.ForeignKeyConstraint(["wallet_id"], ["student_wallets.id"], ondelete="CASCADE", name="fk_wallet_entries_wallet_id_student_wallets"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_wallet_entries_student_id_students"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_wallet_entries_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_wallet_entries_created_by_users"),
    )
    op.create_index("ix_wallet_entries_id", "wallet_entries", ["id"])
    op.create_index("ix_wallet_entries_org_id", "wallet_entries", ["org_id"])
    op.create_index("ix_wallet_entries_wallet_id", "wallet_entries", ["wallet_id"])
    op.create_index("ix_wallet_entries_student_id", "wallet_entries", ["student_id"])
    op.create_index("ix_wallet_entries_student_org", "wallet_entries", ["student_id", "org_id"])
    op.create_index("ix_wallet_entries_wallet_org", "wallet_entries", ["wallet_id", "org_id"])

    op.create_table(
        "cooperative_members",
        *_base(),
        sa.Column("member_user_id", sa.String(36), nullable=True),
        sa.Column("member_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("joined_on", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cooperative_members"),
        sa.ForeignKeyConstraint(["member_user_id"], ["users.id"], ondelete="SET NULL", name="fk_cooperative_members_member_user_id_users"),
    )
    op.create_index("ix_cooperative_members_id", "cooperative_members", ["id"])
    op.create_index("ix_cooperative_members_org_id", "cooperative_members", ["org_id"])
    op.create_index("ix_cooperative_members_org", "cooperative_members", ["org_id"])

    op.create_table(
        "coop_entries",
        *_base(),
        sa.Column("member_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("signed_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_coop_entries"),
        sa.ForeignKeyConstraint(["member_id"], ["cooperative_members.id"], ondelete="CASCADE", name="fk_coop_entries_member_id_cooperative_members"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL", name="fk_coop_entries_journal_entry_id_journal_entries"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_coop_entries_created_by_users"),
    )
    op.create_index("ix_coop_entries_id", "coop_entries", ["id"])
    op.create_index("ix_coop_entries_org_id", "coop_entries", ["org_id"])
    op.create_index("ix_coop_entries_member_id", "coop_entries", ["member_id"])
    op.create_index("ix_coop_entries_member_org", "coop_entries", ["member_id", "org_id"])


def downgrade() -> None:
    for ix in ["ix_coop_entries_member_org", "ix_coop_entries_member_id", "ix_coop_entries_org_id", "ix_coop_entries_id"]:
        op.drop_index(ix, table_name="coop_entries")
    op.drop_table("coop_entries")
    for ix in ["ix_cooperative_members_org", "ix_cooperative_members_org_id", "ix_cooperative_members_id"]:
        op.drop_index(ix, table_name="cooperative_members")
    op.drop_table("cooperative_members")
    for ix in ["ix_wallet_entries_wallet_org", "ix_wallet_entries_student_org", "ix_wallet_entries_student_id",
               "ix_wallet_entries_wallet_id", "ix_wallet_entries_org_id", "ix_wallet_entries_id"]:
        op.drop_index(ix, table_name="wallet_entries")
    op.drop_table("wallet_entries")
    for ix in ["ix_student_wallets_student_org", "ix_student_wallets_student_id", "ix_student_wallets_org_id", "ix_student_wallets_id"]:
        op.drop_index(ix, table_name="student_wallets")
    op.drop_table("student_wallets")
