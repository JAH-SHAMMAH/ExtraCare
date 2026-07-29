"""Pastoral Batch F-2: Roll Call + Pastoral Report + Remarks

Revision ID: 107_pastoral_rollcall_report
Revises: 106_pastoral_leadership_heads
Create Date: 2026-07-29 14:00:00.000000

Boarding roll-call marks + pastoral report remark bank + per-student term remarks.
Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "107_pastoral_rollcall_report"
down_revision = "106_pastoral_leadership_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hostel_roll_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("hostel_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("roll_date", sa.Date(), nullable=False),
        sa.Column("session", sa.String(length=20), nullable=False, server_default="evening"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="present"),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hostel_id"], ["hostels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "student_id", "roll_date", "session", name="uq_roll_call"),
    )
    op.create_index("ix_hostel_roll_calls_hostel_id", "hostel_roll_calls", ["hostel_id"])
    op.create_index("ix_hostel_roll_calls_student_id", "hostel_roll_calls", ["student_id"])
    op.create_index("ix_hostel_roll_calls_roll_date", "hostel_roll_calls", ["roll_date"])
    op.create_index("ix_roll_calls_hostel_date", "hostel_roll_calls", ["hostel_id", "roll_date"])

    op.create_table(
        "pastoral_remark_bank",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pastoral_remark_bank_org_id", "pastoral_remark_bank", ["org_id"])

    op.create_table(
        "pastoral_remarks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("term", sa.String(length=60), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("recorded_on", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pastoral_remarks_student_id", "pastoral_remarks", ["student_id"])
    op.create_index("ix_pastoral_remarks_student_org", "pastoral_remarks", ["student_id", "org_id"])


def downgrade() -> None:
    op.drop_table("pastoral_remarks")
    op.drop_table("pastoral_remark_bank")
    op.drop_table("hostel_roll_calls")
