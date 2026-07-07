"""Add department/credit_hours/is_active/teacher_name to subjects

Revision ID: 033_add_subject_fields
Revises: 032_add_class_section
Create Date: 2026-07-07 10:00:00.000000

Additive + reversible. The Subject Management UI captures a department, credit
hours, an active flag, and a free-text teacher name, but the subjects table only
had name/code/description/teacher_id — so those edits had nowhere to persist.
This backs them, alongside implementing the missing /school/subjects CRUD.
Existing rows default to credit_hours=1, is_active=true.
"""

from alembic import op
import sqlalchemy as sa


revision = "033_add_subject_fields"
down_revision = "032_add_class_section"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subjects", sa.Column("department", sa.String(100), nullable=True))
    op.add_column("subjects", sa.Column("credit_hours", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("subjects", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("subjects", sa.Column("teacher_name", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("subjects", "teacher_name")
    op.drop_column("subjects", "is_active")
    op.drop_column("subjects", "credit_hours")
    op.drop_column("subjects", "department")
