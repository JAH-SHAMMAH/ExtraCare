"""Secondary Report T-1: PC-teacher lookup (Teacher Comments gate)

Revision ID: 116_class_pc_teacher
Revises: 115_report_comments_store
Create Date: 2026-08-02 10:00:00.000000

A per-class PC (pastoral-care) teacher assignment. Empty by default -> the gate
resolver falls back to the class/form teacher; overridable as data later. Additive.
"""
from alembic import op
import sqlalchemy as sa


revision = "116_class_pc_teacher"
down_revision = "115_report_comments_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_pc_teachers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("class_id", sa.String(length=36), nullable=False),
        sa.Column("teacher_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "class_id", name="uq_class_pc_teacher"),
    )
    op.create_index("ix_class_pc_teachers_class_id", "class_pc_teachers", ["class_id"])
    op.create_index("ix_class_pc_teachers_teacher_id", "class_pc_teachers", ["teacher_id"])


def downgrade() -> None:
    op.drop_table("class_pc_teachers")
