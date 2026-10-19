"""Question answer option type: text box or file upload

Revision ID: 150_answer_option_type
Revises: 149_question_bank_extras
"""
import sqlalchemy as sa
from alembic import op

revision = "150_answer_option_type"
down_revision = "149_question_bank_extras"
branch_labels = None
depends_on = None


def _has(table, col):
    return col in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for t in ("cbt_question_bank", "cbt_questions"):
        if not _has(t, "answer_type"):
            op.add_column(t, sa.Column("answer_type", sa.String(10), nullable=False, server_default="text"))


def downgrade() -> None:
    for t in ("cbt_questions", "cbt_question_bank"):
        op.drop_column(t, "answer_type")
