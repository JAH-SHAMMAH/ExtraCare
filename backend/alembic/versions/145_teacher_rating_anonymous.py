"""teacher_ratings.is_anonymous: a pupil may hide their name from the school

Revision ID: 145_teacher_rating_anonymous
Revises: 144_seed_term_days_and_clubs
"""
import sqlalchemy as sa
from alembic import op

revision = "145_teacher_rating_anonymous"
down_revision = "144_seed_term_days_and_clubs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("teacher_ratings")}
    if "is_anonymous" not in cols:
        op.add_column("teacher_ratings", sa.Column(
            "is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("teacher_ratings", "is_anonymous")
