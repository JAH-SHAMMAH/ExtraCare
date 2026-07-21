"""Access Control config: staff_attendance_settings

Revision ID: 079_staff_attendance_settings
Revises: 078_criterion_competency
Create Date: 2026-07-21 12:00:00.000000

Additive + reversible. One-row-per-org staff clock configuration (work hours,
late grace, geofencing). Matches TenantMixin — org_id is an indexed String.
"""
from alembic import op
import sqlalchemy as sa


revision = "079_staff_attendance_settings"
down_revision = "078_criterion_competency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_attendance_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("work_start_time", sa.Time(), nullable=True),
        sa.Column("work_end_time", sa.Time(), nullable=True),
        sa.Column("late_grace_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("geofence_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("geofence_lat", sa.Float(), nullable=True),
        sa.Column("geofence_lng", sa.Float(), nullable=True),
        sa.Column("geofence_radius_m", sa.Integer(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_staff_attendance_settings_org"),
    )
    op.create_index("ix_staff_attendance_settings_org_id", "staff_attendance_settings", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_attendance_settings_org_id", table_name="staff_attendance_settings")
    op.drop_table("staff_attendance_settings")
