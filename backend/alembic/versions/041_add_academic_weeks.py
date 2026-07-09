"""Create academic_weeks (Week Entries registry)

Revision ID: 041_academic_weeks
Revises: 040_normalize_term_extra
Create Date: 2026-07-08 17:00:00.000000

Additive + reversible. Standalone academic-week registry for Admin Management →
Manage Week Entries. Nothing FKs into it yet (weekly remarks/reflections keep
their raw week_start dates); a (org, year, term, week_number) uniqueness slot
keeps the calendar clean.
"""

from alembic import op
import sqlalchemy as sa


revision = "041_academic_weeks"
down_revision = "040_normalize_term_extra"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "academic_weeks",
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("is_holiday", sa.Boolean(), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_weeks")),
        sa.UniqueConstraint("org_id", "academic_year", "term", "week_number", name="uq_academic_weeks_slot"),
    )
    with op.batch_alter_table("academic_weeks", schema=None) as b:
        b.create_index(b.f("ix_academic_weeks_id"), ["id"], unique=False)
        b.create_index(b.f("ix_academic_weeks_org_id"), ["org_id"], unique=False)
        b.create_index("ix_academic_weeks_org_term", ["org_id", "academic_year", "term"], unique=False)


def downgrade() -> None:
    op.drop_table("academic_weeks")
