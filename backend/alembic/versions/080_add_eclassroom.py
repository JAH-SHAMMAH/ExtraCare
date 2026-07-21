"""eClassroom module: settings + programs + schedules

Revision ID: 080_eclassroom
Revises: 079_staff_attendance_settings
Create Date: 2026-07-21 12:00:00.000000

Additive + reversible. The virtual-classroom module — per-org settings, learning
programs, and scheduled sessions (which link to a LiveSession when they go live).
Matches TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "080_eclassroom"
down_revision = "079_staff_attendance_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eclassroom_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("can_teacher_publish", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("automatic_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("learning_program_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_eclassroom_settings_org"),
    )
    op.create_index("ix_eclassroom_settings_org_id", "eclassroom_settings", ["org_id"])

    op.create_table(
        "eclassroom_programs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cbt_type", sa.String(length=20), nullable=False, server_default="student"),
        sa.Column("section_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["academic_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eclassroom_programs_org_id", "eclassroom_programs", ["org_id"])
    op.create_index("ix_eclassroom_programs_section_id", "eclassroom_programs", ["section_id"])
    op.create_index("ix_eclassroom_programs_session_id", "eclassroom_programs", ["session_id"])
    op.create_index("ix_eclassroom_programs_org_session", "eclassroom_programs", ["org_id", "session_id"])

    op.create_table(
        "eclassroom_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("section_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("year_group_id", sa.String(length=36), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("live_session_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["academic_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["year_group_id"], ["year_groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["live_session_id"], ["live_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_eclassroom_schedules_org_id", "eclassroom_schedules", ["org_id"])
    op.create_index("ix_eclassroom_schedules_section_id", "eclassroom_schedules", ["section_id"])
    op.create_index("ix_eclassroom_schedules_session_id", "eclassroom_schedules", ["session_id"])
    op.create_index("ix_eclassroom_schedules_year_group_id", "eclassroom_schedules", ["year_group_id"])
    op.create_index("ix_eclassroom_schedules_live_session_id", "eclassroom_schedules", ["live_session_id"])
    op.create_index("ix_eclassroom_schedules_org_status", "eclassroom_schedules", ["org_id", "status"])


def downgrade() -> None:
    for ix in ("org_status", "live_session_id", "year_group_id", "session_id", "section_id", "org_id"):
        op.drop_index(f"ix_eclassroom_schedules_{ix}", table_name="eclassroom_schedules")
    op.drop_table("eclassroom_schedules")
    for ix in ("org_session", "session_id", "section_id", "org_id"):
        op.drop_index(f"ix_eclassroom_programs_{ix}", table_name="eclassroom_programs")
    op.drop_table("eclassroom_programs")
    op.drop_index("ix_eclassroom_settings_org_id", table_name="eclassroom_settings")
    op.drop_table("eclassroom_settings")
