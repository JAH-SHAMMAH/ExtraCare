"""students.other_name (middle / other names, as on Educare's student list)

Revision ID: 157_student_other_name
Revises: 156_class_assistants
"""
import sqlalchemy as sa
from alembic import op

revision = "157_student_other_name"
down_revision = "156_class_assistants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("students")}
    if "other_name" not in cols:
        op.add_column("students", sa.Column("other_name", sa.String(100), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("students")}
    if "other_name" in cols:
        op.drop_column("students", "other_name")
