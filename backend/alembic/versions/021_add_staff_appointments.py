"""Add staff_appointments (HR: Appointment Manager)

Revision ID: 021_add_staff_appointments
Revises: 020_add_fee_discounts
Create Date: 2026-07-04 11:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "021_add_staff_appointments"
down_revision = "020_add_fee_discounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_appointments",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("staff_user_id", sa.String(36), nullable=False),
        sa.Column("appointment_type", sa.String(30), nullable=False, server_default="appointment"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("grade", sa.String(60), nullable=True),
        sa.Column("salary", sa.Numeric(14, 2), nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True, server_default="NGN"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_staff_appointments"),
        sa.ForeignKeyConstraint(["staff_user_id"], ["users.id"], ondelete="CASCADE", name="fk_staff_appointments_staff_user_id_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL", name="fk_staff_appointments_created_by_users"),
    )
    op.create_index("ix_staff_appointments_id", "staff_appointments", ["id"])
    op.create_index("ix_staff_appointments_org_id", "staff_appointments", ["org_id"])
    op.create_index("ix_staff_appointments_staff_user_id", "staff_appointments", ["staff_user_id"])
    op.create_index("ix_staff_appointments_org_staff", "staff_appointments", ["org_id", "staff_user_id"])


def downgrade() -> None:
    op.drop_table("staff_appointments")
