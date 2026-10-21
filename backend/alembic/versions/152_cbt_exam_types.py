"""cbt: exam_type (exam/test/mock/practice) + exam-room integrity counters

Revision ID: 152_cbt_exam_types
Revises: 151_teaching_assignments
"""
import sqlalchemy as sa
from alembic import op

revision = "152_cbt_exam_types"
down_revision = "151_teaching_assignments"
branch_labels = None
depends_on = None


def _cols(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "exam_type" not in _cols("cbt_exams"):
        op.add_column("cbt_exams", sa.Column("exam_type", sa.String(length=12), nullable=False, server_default="exam"))
        op.create_index("ix_cbt_exams_exam_type", "cbt_exams", ["exam_type"])
    have = _cols("cbt_attempts")
    for name in ("idle_count", "blur_count", "paste_count"):
        if name not in have:
            op.add_column("cbt_attempts", sa.Column(name, sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    for name in ("paste_count", "blur_count", "idle_count"):
        op.drop_column("cbt_attempts", name)
    op.drop_index("ix_cbt_exams_exam_type", table_name="cbt_exams")
    op.drop_column("cbt_exams", "exam_type")
