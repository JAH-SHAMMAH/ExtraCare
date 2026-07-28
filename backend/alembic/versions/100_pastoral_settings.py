"""Pastoral Setup: pastoral_settings (Exeat + Default Settings flags)

Revision ID: 100_pastoral_settings
Revises: 099_teacher_sections
Create Date: 2026-07-28 09:00:00.000000

One row per org holding the Pastoral Setup flag groups + the School-Nurse role
pointer. Additive; mirrors behaviour_settings.
"""
from alembic import op
import sqlalchemy as sa


revision = "100_pastoral_settings"
down_revision = "099_teacher_sections"
branch_labels = None
depends_on = None

_BOOLS = [
    ("enable_head_only_approval", sa.false()),
    ("notify_parent_on_exeat_approval", sa.true()),
    ("notify_house_parent_on_exeat_approval", sa.false()),
    ("notify_pastoral_head_on_new_request", sa.true()),
    ("enable_tutorial_week", sa.false()),
    ("email_parent_on_new_point_entry", sa.false()),
    ("enable_academic_cohesion", sa.false()),
    ("show_award_in_point_analysis", sa.false()),
    ("allow_referral_in_mentor_comment", sa.true()),
    ("enable_point_category", sa.false()),
    ("enable_mentor_report_assessment", sa.false()),
    ("allow_only_merits_in_point_entry", sa.false()),
    ("allow_observation_in_mentor_comment", sa.true()),
]


def upgrade() -> None:
    op.create_table(
        "pastoral_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        *[sa.Column(name, sa.Boolean(), nullable=False, server_default=default) for name, default in _BOOLS],
        sa.Column("school_nurse_role_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["school_nurse_role_id"], ["roles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_pastoral_settings_org"),
    )
    op.create_index("ix_pastoral_settings_org_id", "pastoral_settings", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_pastoral_settings_org_id", table_name="pastoral_settings")
    op.drop_table("pastoral_settings")
