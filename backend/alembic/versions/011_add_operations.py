"""Add operations tables: calendar, facility, visitor, collection (Batch 6, non-financial)

Revision ID: 011_add_operations
Revises: 010_add_wallet_cooperative
Create Date: 2026-06-21 07:00:00.000000

Additive + reversible. Visitor + student-collection rows are soft-deletable only
(safeguarding) — they keep the is_deleted/deleted_at columns.
"""

from alembic import op
import sqlalchemy as sa


revision = "011_add_operations"
down_revision = "010_add_wallet_cooperative"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def _soft():
    return (
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    op.create_table(
        "calendar_events", *_base(), *_soft(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("audience", sa.String(40), nullable=True, server_default="school"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_calendar_events"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_calendar_events_created_by_users"),
    )
    op.create_index("ix_calendar_events_id", "calendar_events", ["id"])
    op.create_index("ix_calendar_events_org_id", "calendar_events", ["org_id"])
    op.create_index("ix_calendar_events_start_at", "calendar_events", ["start_at"])
    op.create_index("ix_calendar_events_org_start", "calendar_events", ["org_id", "start_at"])

    op.create_table(
        "facilities", *_base(), *_soft(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("type", sa.String(40), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id", name="pk_facilities"),
    )
    op.create_index("ix_facilities_id", "facilities", ["id"])
    op.create_index("ix_facilities_org_id", "facilities", ["org_id"])
    op.create_index("ix_facilities_org", "facilities", ["org_id"])

    op.create_table(
        "facility_bookings", *_base(),
        sa.Column("facility_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("booked_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_facility_bookings"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="CASCADE", name="fk_facility_bookings_facility_id_facilities"),
        sa.ForeignKeyConstraint(["booked_by"], ["users.id"], ondelete="SET NULL", name="fk_facility_bookings_booked_by_users"),
    )
    op.create_index("ix_facility_bookings_id", "facility_bookings", ["id"])
    op.create_index("ix_facility_bookings_org_id", "facility_bookings", ["org_id"])
    op.create_index("ix_facility_bookings_facility_id", "facility_bookings", ["facility_id"])
    op.create_index("ix_facility_bookings_facility_org", "facility_bookings", ["facility_id", "org_id"])

    op.create_table(
        "visitor_logs", *_base(), *_soft(),
        sa.Column("visitor_name", sa.String(200), nullable=False),
        sa.Column("organization", sa.String(200), nullable=True),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("host_name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("badge_no", sa.String(40), nullable=True),
        sa.Column("sign_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sign_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="signed_in"),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_visitor_logs"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_visitor_logs_recorded_by_users"),
    )
    op.create_index("ix_visitor_logs_id", "visitor_logs", ["id"])
    op.create_index("ix_visitor_logs_org_id", "visitor_logs", ["org_id"])
    op.create_index("ix_visitor_logs_org_status", "visitor_logs", ["org_id", "status"])

    op.create_table(
        "student_collections", *_base(), *_soft(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("collector_name", sa.String(200), nullable=False),
        sa.Column("relationship_to_student", sa.String(80), nullable=True),
        sa.Column("authorized_by", sa.String(36), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_student_collections"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_student_collections_student_id_students"),
        sa.ForeignKeyConstraint(["authorized_by"], ["users.id"], ondelete="SET NULL", name="fk_student_collections_authorized_by_users"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_student_collections_recorded_by_users"),
    )
    op.create_index("ix_student_collections_id", "student_collections", ["id"])
    op.create_index("ix_student_collections_org_id", "student_collections", ["org_id"])
    op.create_index("ix_student_collections_student_id", "student_collections", ["student_id"])
    op.create_index("ix_student_collections_student_org", "student_collections", ["student_id", "org_id"])
    op.create_index("ix_student_collections_org", "student_collections", ["org_id"])


def downgrade() -> None:
    for ix in ["ix_student_collections_org", "ix_student_collections_student_org", "ix_student_collections_student_id",
               "ix_student_collections_org_id", "ix_student_collections_id"]:
        op.drop_index(ix, table_name="student_collections")
    op.drop_table("student_collections")
    for ix in ["ix_visitor_logs_org_status", "ix_visitor_logs_org_id", "ix_visitor_logs_id"]:
        op.drop_index(ix, table_name="visitor_logs")
    op.drop_table("visitor_logs")
    for ix in ["ix_facility_bookings_facility_org", "ix_facility_bookings_facility_id", "ix_facility_bookings_org_id", "ix_facility_bookings_id"]:
        op.drop_index(ix, table_name="facility_bookings")
    op.drop_table("facility_bookings")
    for ix in ["ix_facilities_org", "ix_facilities_org_id", "ix_facilities_id"]:
        op.drop_index(ix, table_name="facilities")
    op.drop_table("facilities")
    for ix in ["ix_calendar_events_org_start", "ix_calendar_events_start_at", "ix_calendar_events_org_id", "ix_calendar_events_id"]:
        op.drop_index(ix, table_name="calendar_events")
    op.drop_table("calendar_events")
