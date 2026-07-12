"""Students (Educare parity): authorized-pickup registry

Revision ID: 054_student_pickups
Revises: 053_facility_management
Create Date: 2026-07-12 10:00:00.000000

Additive + reversible. One table backing "Manage Students Pickup" — the registry
of people authorised to collect a student. Registry only (no per-day pickup log).
Deactivate-not-delete via ``is_active``.
"""
from alembic import op
import sqlalchemy as sa


revision = "054_student_pickups"
down_revision = "053_facility_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_authorized_pickups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("id_document", sa.String(length=120), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_authorized_pickups_student_id", "student_authorized_pickups", ["student_id"])
    op.create_index("ix_student_authorized_pickups_org_id", "student_authorized_pickups", ["org_id"])
    op.create_index("ix_student_pickups_student_org", "student_authorized_pickups", ["student_id", "org_id"])


def downgrade() -> None:
    op.drop_index("ix_student_pickups_student_org", table_name="student_authorized_pickups")
    op.drop_index("ix_student_authorized_pickups_org_id", table_name="student_authorized_pickups")
    op.drop_index("ix_student_authorized_pickups_student_id", table_name="student_authorized_pickups")
    op.drop_table("student_authorized_pickups")
