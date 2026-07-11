"""Drop crm_contacts — CRM is now a thin view over Admissions & Enquiries

Revision ID: 052_drop_crm_contacts
Revises: 051_feedback_module_extras
Create Date: 2026-07-10 19:00:00.000000

The standalone CRMContact table (added in 051) duplicated the prospective-parent
enquiry pipeline already owned by AdmissionApplication (contact + source + a
status stage pipeline + notes). Removed to avoid two competing enquiry systems;
the "CRM" surface is now a thin view over admission-application data. The table
was brand-new and never populated in production.
"""
from alembic import op
import sqlalchemy as sa


revision = "052_drop_crm_contacts"
down_revision = "051_feedback_module_extras"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_crm_contacts_org_stage", table_name="crm_contacts")
    op.drop_index("ix_crm_contacts_email", table_name="crm_contacts")
    op.drop_table("crm_contacts")


def downgrade() -> None:
    op.create_table(
        "crm_contacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("contact_type", sa.String(length=40), nullable=False, server_default="prospective_parent"),
        sa.Column("stage", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("assigned_to", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crm_contacts_email", "crm_contacts", ["email"])
    op.create_index("ix_crm_contacts_org_stage", "crm_contacts", ["org_id", "stage"])
