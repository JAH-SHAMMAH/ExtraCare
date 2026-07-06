"""Add pickup_points + pickups (Store: Pickup Unit)

Revision ID: 028_add_pickups
Revises: 027_add_warehouses
Create Date: 2026-07-04 16:45:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "028_add_pickups"
down_revision = "027_add_warehouses"
branch_labels = None
depends_on = None


def _base():
    return (
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def upgrade() -> None:
    op.create_table(
        "pickup_points", *_base(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pickup_points"),
    )
    op.create_index("ix_pickup_points_id", "pickup_points", ["id"])
    op.create_index("ix_pickup_points_org_id", "pickup_points", ["org_id"])
    op.create_index("ix_pickup_points_org", "pickup_points", ["org_id"])

    op.create_table(
        "pickups", *_base(),
        sa.Column("pickup_point_id", sa.String(36), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("customer_name", sa.String(200), nullable=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("reference", sa.String(60), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_by", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pickups"),
        sa.ForeignKeyConstraint(["pickup_point_id"], ["pickup_points.id"], ondelete="SET NULL", name="fk_pickups_point"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL", name="fk_pickups_student"),
        sa.ForeignKeyConstraint(["collected_by"], ["users.id"], ondelete="SET NULL", name="fk_pickups_collected_by"),
    )
    op.create_index("ix_pickups_id", "pickups", ["id"])
    op.create_index("ix_pickups_org_id", "pickups", ["org_id"])
    op.create_index("ix_pickups_pickup_point_id", "pickups", ["pickup_point_id"])
    op.create_index("ix_pickups_org_status", "pickups", ["org_id", "status"])


def downgrade() -> None:
    op.drop_table("pickups")
    op.drop_table("pickup_points")
