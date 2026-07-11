"""Facility Management (Educare parity): lookups + role pools + workflow chain

Revision ID: 053_facility_management
Revises: 052_drop_crm_contacts
Create Date: 2026-07-10 21:00:00.000000

Additive + reversible. Extends `facilities` (facility_type_id, quantity) and adds
the managed lookups (types/locations/departments), role-assignment pools, and the
Complaint → Inspection → Maintenance → Requisition workflow chain + tiered
approval levels. Audit Trail reuses the global AuditLog (no table here); a
requisition's disbursement reuses the finance ledger (journal_entry_id link).
"""
from alembic import op
import sqlalchemy as sa


revision = "053_facility_management"
down_revision = "052_drop_crm_contacts"
branch_labels = None
depends_on = None


def _org_fk():
    return sa.ForeignKeyConstraint(["org_id"], ["organizations.id"])


def upgrade() -> None:
    op.create_table(
        "facility_types",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_types_org_id", "facility_types", ["org_id"])

    op.create_table(
        "facility_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_locations_org_id", "facility_locations", ["org_id"])

    op.create_table(
        "facility_departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_departments_org_id", "facility_departments", ["org_id"])

    op.create_table(
        "facility_approval_levels",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("threshold", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("handler_id", sa.String(length=36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["handler_id"], ["users.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_approval_levels_org_id", "facility_approval_levels", ["org_id"])

    op.create_table(
        "facility_staff",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_type", sa.String(length=30), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["facility_departments.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_type", "department_id", name="uq_facility_staff"),
    )
    op.create_index("ix_facility_staff_user_id", "facility_staff", ["user_id"])
    op.create_index("ix_facility_staff_org_role", "facility_staff", ["org_id", "role_type"])

    op.create_table(
        "facility_location_tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("facility_id", sa.String(length=36), nullable=False),
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["facility_locations.id"], ondelete="CASCADE"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("facility_id", "location_id", name="uq_facility_location_tag"),
    )
    op.create_index("ix_facility_location_tags_facility_id", "facility_location_tags", ["facility_id"])
    op.create_index("ix_facility_location_tags_location_id", "facility_location_tags", ["location_id"])
    op.create_index("ix_facility_location_tags_org_id", "facility_location_tags", ["org_id"])

    op.create_table(
        "facility_manager_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("facility_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("facility_id", "user_id", name="uq_facility_manager_link"),
    )
    op.create_index("ix_facility_manager_links_facility_id", "facility_manager_links", ["facility_id"])
    op.create_index("ix_facility_manager_links_user_id", "facility_manager_links", ["user_id"])
    op.create_index("ix_facility_manager_links_org_id", "facility_manager_links", ["org_id"])

    op.create_table(
        "facility_complaints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("facility_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("lodged_by", sa.String(length=36), nullable=True),
        sa.Column("date_lodged", sa.Date(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lodged_by"], ["users.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_complaints_reference", "facility_complaints", ["reference"])
    op.create_index("ix_facility_complaints_facility_id", "facility_complaints", ["facility_id"])
    op.create_index("ix_facility_complaints_lodged_by", "facility_complaints", ["lodged_by"])
    op.create_index("ix_facility_complaints_org_status", "facility_complaints", ["org_id", "status"])

    op.create_table(
        "facility_inspections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("facility_id", sa.String(length=36), nullable=True),
        sa.Column("inspector_id", sa.String(length=36), nullable=True),
        sa.Column("complaint_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(length=30), nullable=True),
        sa.Column("inspection_date", sa.Date(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["inspector_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["complaint_id"], ["facility_complaints.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_inspections_facility_id", "facility_inspections", ["facility_id"])
    op.create_index("ix_facility_inspections_inspector_id", "facility_inspections", ["inspector_id"])
    op.create_index("ix_facility_inspections_complaint_id", "facility_inspections", ["complaint_id"])
    op.create_index("ix_facility_inspections_org_id", "facility_inspections", ["org_id"])

    op.create_table(
        "facility_maintenance",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("facility_id", sa.String(length=36), nullable=True),
        sa.Column("complaint_id", sa.String(length=36), nullable=True),
        sa.Column("maintenance_type", sa.String(length=80), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("total_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("request_date", sa.Date(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["complaint_id"], ["facility_complaints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_maintenance_facility_id", "facility_maintenance", ["facility_id"])
    op.create_index("ix_facility_maintenance_complaint_id", "facility_maintenance", ["complaint_id"])
    op.create_index("ix_facility_maintenance_requested_by", "facility_maintenance", ["requested_by"])
    op.create_index("ix_facility_maintenance_org_status", "facility_maintenance", ["org_id", "status"])

    op.create_table(
        "facility_requisitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("reference", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("maintenance_id", sa.String(length=36), nullable=True),
        sa.Column("maintenance_type", sa.String(length=80), nullable=True),
        sa.Column("maintenance_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("requisition_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("approval_level_id", sa.String(length=36), nullable=True),
        sa.Column("total_approved", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("approval_date", sa.Date(), nullable=True),
        sa.Column("total_disbursed", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["maintenance_id"], ["facility_maintenance.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approval_level_id"], ["facility_approval_levels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["journal_entry_id"], ["journal_entries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        _org_fk(), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facility_requisitions_reference", "facility_requisitions", ["reference"])
    op.create_index("ix_facility_requisitions_maintenance_id", "facility_requisitions", ["maintenance_id"])
    op.create_index("ix_facility_requisitions_requested_by", "facility_requisitions", ["requested_by"])
    op.create_index("ix_facility_requisitions_org_status", "facility_requisitions", ["org_id", "status"])

    with op.batch_alter_table("facilities", schema=None) as b:
        b.add_column(sa.Column("facility_type_id", sa.String(length=36), nullable=True))
        b.add_column(sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"))
        b.create_index("ix_facilities_facility_type_id", ["facility_type_id"])
        b.create_foreign_key("fk_facilities_facility_type_id", "facility_types", ["facility_type_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("facilities", schema=None) as b:
        b.drop_constraint("fk_facilities_facility_type_id", type_="foreignkey")
        b.drop_index("ix_facilities_facility_type_id")
        b.drop_column("quantity")
        b.drop_column("facility_type_id")

    for tbl in ("facility_requisitions", "facility_maintenance", "facility_inspections",
                "facility_complaints", "facility_manager_links", "facility_location_tags",
                "facility_staff", "facility_approval_levels", "facility_departments",
                "facility_locations", "facility_types"):
        op.drop_table(tbl)
