"""Add warehouses + warehouse_stock (Store: Warehouse module)

Revision ID: 027_add_warehouses
Revises: 026_add_cashier_role
Create Date: 2026-07-04 16:00:00.000000

Additive + reversible.
"""

from alembic import op
import sqlalchemy as sa


revision = "027_add_warehouses"
down_revision = "026_add_cashier_role"
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
        "warehouses", *_base(),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_warehouses"),
    )
    op.create_index("ix_warehouses_id", "warehouses", ["id"])
    op.create_index("ix_warehouses_org_id", "warehouses", ["org_id"])
    op.create_index("ix_warehouses_org", "warehouses", ["org_id"])

    op.create_table(
        "warehouse_stock", *_base(),
        sa.Column("warehouse_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id", name="pk_warehouse_stock"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="CASCADE", name="fk_warehouse_stock_wh"),
        sa.ForeignKeyConstraint(["item_id"], ["store_items.id"], ondelete="CASCADE", name="fk_warehouse_stock_item"),
        sa.UniqueConstraint("warehouse_id", "item_id", name="uq_warehouse_stock_wh_item"),
    )
    op.create_index("ix_warehouse_stock_id", "warehouse_stock", ["id"])
    op.create_index("ix_warehouse_stock_org_id", "warehouse_stock", ["org_id"])
    op.create_index("ix_warehouse_stock_warehouse_id", "warehouse_stock", ["warehouse_id"])
    op.create_index("ix_warehouse_stock_item_id", "warehouse_stock", ["item_id"])
    op.create_index("ix_warehouse_stock_org", "warehouse_stock", ["org_id"])


def downgrade() -> None:
    op.drop_table("warehouse_stock")
    op.drop_table("warehouses")
