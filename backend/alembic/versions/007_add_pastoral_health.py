"""Add pastoral, boarding & health tables (Batch 4)

Revision ID: 007_add_pastoral_health
Revises: 006_add_academic_records
Create Date: 2026-06-21 03:00:00.000000

Additive + reversible. Creates: hostels, boarding_allocations, exeat_requests,
mentor_reports, medical_records. Touches no existing table.
"""

from alembic import op
import sqlalchemy as sa


revision = "007_add_pastoral_health"
down_revision = "006_add_academic_records"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "hostels",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("warden_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_hostels"),
        sa.ForeignKeyConstraint(["warden_id"], ["users.id"], ondelete="SET NULL", name="fk_hostels_warden_id_users"),
    )
    op.create_index("ix_hostels_id", "hostels", ["id"])
    op.create_index("ix_hostels_org_id", "hostels", ["org_id"])
    op.create_index("ix_hostels_org", "hostels", ["org_id"])

    op.create_table(
        "boarding_allocations",
        *_base(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("hostel_id", sa.String(36), nullable=False),
        sa.Column("room", sa.String(40), nullable=True),
        sa.Column("bed", sa.String(40), nullable=True),
        sa.Column("allocated_on", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allocated_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_boarding_allocations"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_boarding_allocations_student_id_students"),
        sa.ForeignKeyConstraint(["hostel_id"], ["hostels.id"], ondelete="CASCADE", name="fk_boarding_allocations_hostel_id_hostels"),
        sa.ForeignKeyConstraint(["allocated_by"], ["users.id"], ondelete="SET NULL", name="fk_boarding_allocations_allocated_by_users"),
    )
    op.create_index("ix_boarding_allocations_id", "boarding_allocations", ["id"])
    op.create_index("ix_boarding_allocations_org_id", "boarding_allocations", ["org_id"])
    op.create_index("ix_boarding_allocations_student_id", "boarding_allocations", ["student_id"])
    op.create_index("ix_boarding_allocations_hostel_id", "boarding_allocations", ["hostel_id"])
    op.create_index("ix_boarding_alloc_hostel_org", "boarding_allocations", ["hostel_id", "org_id"])
    op.create_index("ix_boarding_alloc_student_org", "boarding_allocations", ["student_id", "org_id"])

    op.create_table(
        "exeat_requests",
        *_base(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("destination", sa.String(200), nullable=True),
        sa.Column("depart_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_exeat_requests"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_exeat_requests_student_id_students"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL", name="fk_exeat_requests_requested_by_users"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL", name="fk_exeat_requests_approved_by_users"),
    )
    op.create_index("ix_exeat_requests_id", "exeat_requests", ["id"])
    op.create_index("ix_exeat_requests_org_id", "exeat_requests", ["org_id"])
    op.create_index("ix_exeat_requests_student_id", "exeat_requests", ["student_id"])
    op.create_index("ix_exeat_org_status", "exeat_requests", ["org_id", "status"])
    op.create_index("ix_exeat_student_org", "exeat_requests", ["student_id", "org_id"])

    op.create_table(
        "mentor_reports",
        *_base(),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("mentor_id", sa.String(36), nullable=True),
        sa.Column("term", sa.String(40), nullable=True),
        sa.Column("period", sa.String(60), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("concerns", sa.Text(), nullable=True),
        sa.Column("recommendations", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_mentor_reports"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_mentor_reports_student_id_students"),
        sa.ForeignKeyConstraint(["mentor_id"], ["users.id"], ondelete="SET NULL", name="fk_mentor_reports_mentor_id_users"),
    )
    op.create_index("ix_mentor_reports_id", "mentor_reports", ["id"])
    op.create_index("ix_mentor_reports_org_id", "mentor_reports", ["org_id"])
    op.create_index("ix_mentor_reports_student_id", "mentor_reports", ["student_id"])
    op.create_index("ix_mentor_reports_student_org", "mentor_reports", ["student_id", "org_id"])

    op.create_table(
        "student_medical_records",
        *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("record_type", sa.String(20), nullable=False, server_default="visit"),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("treatment", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("recorded_on", sa.Date(), nullable=True),
        sa.Column("follow_up_on", sa.Date(), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_student_medical_records"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE", name="fk_student_medical_records_student_id_students"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], ondelete="SET NULL", name="fk_student_medical_records_recorded_by_users"),
    )
    op.create_index("ix_student_medical_records_id", "student_medical_records", ["id"])
    op.create_index("ix_student_medical_records_org_id", "student_medical_records", ["org_id"])
    op.create_index("ix_student_medical_records_student_id", "student_medical_records", ["student_id"])
    op.create_index("ix_student_medical_records_student_org", "student_medical_records", ["student_id", "org_id"])
    op.create_index("ix_student_medical_records_org_type", "student_medical_records", ["org_id", "record_type"])


def downgrade() -> None:
    for ix in ["ix_student_medical_records_org_type", "ix_student_medical_records_student_org",
               "ix_student_medical_records_student_id", "ix_student_medical_records_org_id", "ix_student_medical_records_id"]:
        op.drop_index(ix, table_name="student_medical_records")
    op.drop_table("student_medical_records")

    for ix in ["ix_mentor_reports_student_org", "ix_mentor_reports_student_id",
               "ix_mentor_reports_org_id", "ix_mentor_reports_id"]:
        op.drop_index(ix, table_name="mentor_reports")
    op.drop_table("mentor_reports")

    for ix in ["ix_exeat_student_org", "ix_exeat_org_status", "ix_exeat_requests_student_id",
               "ix_exeat_requests_org_id", "ix_exeat_requests_id"]:
        op.drop_index(ix, table_name="exeat_requests")
    op.drop_table("exeat_requests")

    for ix in ["ix_boarding_alloc_student_org", "ix_boarding_alloc_hostel_org",
               "ix_boarding_allocations_hostel_id", "ix_boarding_allocations_student_id",
               "ix_boarding_allocations_org_id", "ix_boarding_allocations_id"]:
        op.drop_index(ix, table_name="boarding_allocations")
    op.drop_table("boarding_allocations")

    for ix in ["ix_hostels_org", "ix_hostels_org_id", "ix_hostels_id"]:
        op.drop_index(ix, table_name="hostels")
    op.drop_table("hostels")
