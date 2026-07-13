"""CBT admin: result remark note on attempts

Revision ID: 062_cbt_remark_note
Revises: 061_section_aliases
Create Date: 2026-07-13 09:00:00.000000

Additive + reversible. Adds cbt_attempts.remark_note — a staff textual remark on
a student's CBT result ("Admin Test Remark"), distinct from the per-answer manual
grading flow.
"""
from alembic import op
import sqlalchemy as sa


revision = "062_cbt_remark_note"
down_revision = "061_section_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cbt_attempts") as batch:
        batch.add_column(sa.Column("remark_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cbt_attempts") as batch:
        batch.drop_column("remark_note")
