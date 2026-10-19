"""Question bank: tags, explanation, is_examination

Revision ID: 149_question_bank_extras
Revises: 148_push_subscriptions
"""
import sqlalchemy as sa
from alembic import op

revision = "149_question_bank_extras"
down_revision = "148_push_subscriptions"
branch_labels = None
depends_on = None


def _cols():
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("cbt_question_bank")}


def upgrade() -> None:
    have = _cols()
    if "tags" not in have:
        op.add_column("cbt_question_bank", sa.Column("tags", sa.JSON(), nullable=True))
    if "explanation" not in have:
        op.add_column("cbt_question_bank", sa.Column("explanation", sa.Text(), nullable=True))
    if "is_examination" not in have:
        op.add_column("cbt_question_bank", sa.Column("is_examination", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for c in ("is_examination", "explanation", "tags"):
        op.drop_column("cbt_question_bank", c)
