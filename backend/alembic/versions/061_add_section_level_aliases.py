"""School Reports R2a: section level aliases (level->section mapping)

Revision ID: 061_section_aliases
Revises: 060_report_templates
Create Date: 2026-07-12 20:00:00.000000

Additive + reversible. Adds school_sections.level_aliases (JSON list of class
`level` values that map to the section), so auto-map links classes by a proper
level->section mapping (section name OR alias), not just an exact name match.
"""
from alembic import op
import sqlalchemy as sa


revision = "061_section_aliases"
down_revision = "060_report_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("school_sections") as batch:
        batch.add_column(sa.Column("level_aliases", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("school_sections") as batch:
        batch.drop_column("level_aliases")
