"""past questions: exam_body/exam_year/external_id on the bank, practice_meta on exams

Revision ID: 153_past_questions
Revises: 152_cbt_exam_types
"""
import sqlalchemy as sa
from alembic import op

revision = "153_past_questions"
down_revision = "152_cbt_exam_types"
branch_labels = None
depends_on = None


def _cols(table):
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    have = _cols("cbt_question_bank")
    if "exam_body" not in have:
        op.add_column("cbt_question_bank", sa.Column("exam_body", sa.String(length=10), nullable=True))
        op.create_index("ix_cbt_question_bank_exam_body", "cbt_question_bank", ["exam_body"])
    if "exam_year" not in have:
        op.add_column("cbt_question_bank", sa.Column("exam_year", sa.Integer(), nullable=True))
    if "external_id" not in have:
        op.add_column("cbt_question_bank", sa.Column("external_id", sa.String(length=60), nullable=True))
    if "practice_meta" not in _cols("cbt_exams"):
        op.add_column("cbt_exams", sa.Column("practice_meta", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("cbt_exams", "practice_meta")
    op.drop_column("cbt_question_bank", "external_id")
    op.drop_column("cbt_question_bank", "exam_year")
    op.drop_index("ix_cbt_question_bank_exam_body", table_name="cbt_question_bank")
    op.drop_column("cbt_question_bank", "exam_body")
