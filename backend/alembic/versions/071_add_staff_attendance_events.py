"""Staff attendance (HR Access Control): staff_attendance_events

Revision ID: 071_staff_attendance
Revises: 070_hr_managed_items
Create Date: 2026-07-20 12:00:00.000000

Additive + reversible. A staff clock-in / clock-out punch log (own table, keyed
to users) mirroring the student AttendanceEvent design. Matches TenantMixin —
org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "071_staff_attendance"
down_revision = "070_hr_managed_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_attendance_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("staff_user_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.Enum("CLOCK_IN", "CLOCK_OUT", name="staffclocktype"), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Enum("MANUAL", "ZKTECO", "IMPORT", "API", name="staffclocksource"), nullable=False, server_default="MANUAL"),
        sa.Column("external_ref", sa.String(length=128), nullable=True),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staff_attendance_events_staff_user_id", "staff_attendance_events", ["staff_user_id"])
    op.create_index("ix_staff_attendance_events_event_time", "staff_attendance_events", ["event_time"])
    op.create_index("ix_staff_attendance_events_external_ref", "staff_attendance_events", ["external_ref"])
    op.create_index("ix_staff_attendance_events_org_id", "staff_attendance_events", ["org_id"])
    op.create_index("ix_staff_attendance_org_staff_time", "staff_attendance_events", ["org_id", "staff_user_id", "event_time"])


def downgrade() -> None:
    op.drop_index("ix_staff_attendance_org_staff_time", table_name="staff_attendance_events")
    op.drop_index("ix_staff_attendance_events_org_id", table_name="staff_attendance_events")
    op.drop_index("ix_staff_attendance_events_external_ref", table_name="staff_attendance_events")
    op.drop_index("ix_staff_attendance_events_event_time", table_name="staff_attendance_events")
    op.drop_index("ix_staff_attendance_events_staff_user_id", table_name="staff_attendance_events")
    op.drop_table("staff_attendance_events")
    sa.Enum(name="staffclocktype").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="staffclocksource").drop(op.get_bind(), checkfirst=True)
