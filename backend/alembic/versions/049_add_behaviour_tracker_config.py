"""Behaviour Tracker config: taxonomy + levels + settings

Revision ID: 049_behaviour_tracker_config
Revises: 048_cbt_gradebook_feed
Create Date: 2026-07-10 14:00:00.000000

Additive + reversible. Backs the dedicated Behaviour Tracker admin section:
- behaviour_categories / behaviour_subcategories — managed taxonomy ("Manage" /
  "Sub-manage behaviourTracker"). behaviour_records gain optional category_id /
  subcategory_id refs; the existing free-text `category` column is kept.
- behaviour_levels — named conduct bands (point ranges) for classification.
- behaviour_settings — per-org module configuration (one row per org).
"""
from alembic import op
import sqlalchemy as sa


revision = "049_behaviour_tracker_config"
down_revision = "048_cbt_gradebook_feed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "behaviour_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False, server_default="POSITIVE"),
        sa.Column("default_points", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_behaviour_categories_org_id", "behaviour_categories", ["org_id"])

    op.create_table(
        "behaviour_subcategories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("default_points", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["behaviour_categories.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_behaviour_subcategories_category_id", "behaviour_subcategories", ["category_id"])
    op.create_index("ix_behaviour_subcategories_org_id", "behaviour_subcategories", ["org_id"])

    op.create_table(
        "behaviour_levels",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("min_points", sa.Integer(), nullable=False),
        sa.Column("max_points", sa.Integer(), nullable=True),
        sa.Column("colour", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_behaviour_levels_org_id", "behaviour_levels", ["org_id"])

    op.create_table(
        "behaviour_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("default_points", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("visible_to_students", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("visible_to_parents", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_derive_levels", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_behaviour_settings_org"),
    )
    op.create_index("ix_behaviour_settings_org_id", "behaviour_settings", ["org_id"])

    with op.batch_alter_table("behaviour_records", schema=None) as b:
        b.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        b.add_column(sa.Column("subcategory_id", sa.String(length=36), nullable=True))
        b.create_index("ix_behaviour_records_category_id", ["category_id"])
        b.create_index("ix_behaviour_records_subcategory_id", ["subcategory_id"])
        b.create_foreign_key(
            "fk_behaviour_records_category_id", "behaviour_categories", ["category_id"], ["id"])
        b.create_foreign_key(
            "fk_behaviour_records_subcategory_id", "behaviour_subcategories", ["subcategory_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("behaviour_records", schema=None) as b:
        b.drop_constraint("fk_behaviour_records_subcategory_id", type_="foreignkey")
        b.drop_constraint("fk_behaviour_records_category_id", type_="foreignkey")
        b.drop_index("ix_behaviour_records_subcategory_id")
        b.drop_index("ix_behaviour_records_category_id")
        b.drop_column("subcategory_id")
        b.drop_column("category_id")

    op.drop_index("ix_behaviour_settings_org_id", table_name="behaviour_settings")
    op.drop_table("behaviour_settings")
    op.drop_index("ix_behaviour_levels_org_id", table_name="behaviour_levels")
    op.drop_table("behaviour_levels")
    op.drop_index("ix_behaviour_subcategories_org_id", table_name="behaviour_subcategories")
    op.drop_index("ix_behaviour_subcategories_category_id", table_name="behaviour_subcategories")
    op.drop_table("behaviour_subcategories")
    op.drop_index("ix_behaviour_categories_org_id", table_name="behaviour_categories")
    op.drop_table("behaviour_categories")
