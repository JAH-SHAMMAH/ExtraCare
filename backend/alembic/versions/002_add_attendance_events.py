"""Add attendance_events table (event-sourced attendance)

Revision ID: 002_add_attendance_events
Revises: 001_add_payment_infrastructure
Create Date: 2026-06-06 00:00:00.000000

Adds the timestamped check-in/check-out event table that backs the
ZKTeco-ready attendance layer. Purely additive and fully reversible:
- creates `attendance_events` and its indexes/unique constraint
- touches no existing table or row

The unique constraint (org_id, source, external_ref) makes device ingestion
idempotent; NULL external_ref (manual entries) stay distinct under SQL NULL
semantics so manual rows never collide.
"""

from alembic import op
import sqlalchemy as sa


# Revision identifiers used by Alembic
revision = "002_add_attendance_events"
down_revision = "001_add_payment_infrastructure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attendance_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.Enum("check_in", "check_out", name="attendanceeventtype"), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Enum("manual", "zkteco", "import", "api", name="attendanceeventsource"), nullable=False, server_default="manual"),
        sa.Column("external_ref", sa.String(128), nullable=True),
        sa.Column("device_id", sa.String(128), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_attendance_events"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_attendance_events_org_id_organizations"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_attendance_events_student_id_students"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_attendance_events_recorded_by_users"),
        sa.UniqueConstraint("org_id", "source", "external_ref", name="uq_attendance_event_source_ref"),
    )
    op.create_index("ix_attendance_events_student_id", "attendance_events", ["student_id"])
    op.create_index("ix_attendance_events_org_id", "attendance_events", ["org_id"])
    op.create_index("ix_attendance_events_event_time", "attendance_events", ["event_time"])
    op.create_index("ix_attendance_events_external_ref", "attendance_events", ["external_ref"])
    op.create_index("ix_attendance_events_student_time", "attendance_events", ["student_id", "event_time"])
    op.create_index("ix_attendance_events_org_time", "attendance_events", ["org_id", "event_time"])


def downgrade() -> None:
    op.drop_index("ix_attendance_events_org_time", table_name="attendance_events")
    op.drop_index("ix_attendance_events_student_time", table_name="attendance_events")
    op.drop_index("ix_attendance_events_external_ref", table_name="attendance_events")
    op.drop_index("ix_attendance_events_event_time", table_name="attendance_events")
    op.drop_index("ix_attendance_events_org_id", table_name="attendance_events")
    op.drop_index("ix_attendance_events_student_id", table_name="attendance_events")
    op.drop_table("attendance_events")
    # Drop the enum types created for this table (no-op on SQLite, which stores
    # enums as VARCHAR; relevant for MySQL/Postgres in production).
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="attendanceeventtype").drop(bind, checkfirst=True)
        sa.Enum(name="attendanceeventsource").drop(bind, checkfirst=True)
