"""Library: settings + categories + locations + book reviews

Revision ID: 067_library_setup_reviews
Revises: 066_lesson_plan_schedules
Create Date: 2026-07-14 17:00:00.000000

Additive + reversible. Backs the Library module's Setup (settings singleton +
managed categories/locations picklists) and Manage Reviews (moderated reader
reviews). Existing books/loans are untouched.
"""
from alembic import op
import sqlalchemy as sa


revision = "067_library_setup_reviews"
down_revision = "066_lesson_plan_schedules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("loan_period_days", sa.Integer(), nullable=False, server_default="14"),
        sa.Column("max_books_per_user", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("allow_reviews", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_needs_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_library_settings_org"),
    )
    op.create_index("ix_library_settings_org_id", "library_settings", ["org_id"], unique=True)

    op.create_table(
        "library_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_library_category_org_name"),
    )
    op.create_index("ix_library_categories_org_id", "library_categories", ["org_id"])

    op.create_table(
        "library_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_library_location_org_name"),
    )
    op.create_index("ix_library_locations_org_id", "library_locations", ["org_id"])

    op.create_table(
        "book_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("book_id", sa.String(length=36), nullable=False),
        sa.Column("reviewer_id", sa.String(length=36), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["book_id"], ["library_books.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_book_reviews_book_id", "book_reviews", ["book_id"])
    op.create_index("ix_book_reviews_reviewer_id", "book_reviews", ["reviewer_id"])
    op.create_index("ix_book_reviews_org_id", "book_reviews", ["org_id"])
    op.create_index("ix_book_reviews_book_status", "book_reviews", ["book_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_book_reviews_book_status", table_name="book_reviews")
    op.drop_index("ix_book_reviews_org_id", table_name="book_reviews")
    op.drop_index("ix_book_reviews_reviewer_id", table_name="book_reviews")
    op.drop_index("ix_book_reviews_book_id", table_name="book_reviews")
    op.drop_table("book_reviews")

    op.drop_index("ix_library_locations_org_id", table_name="library_locations")
    op.drop_table("library_locations")

    op.drop_index("ix_library_categories_org_id", table_name="library_categories")
    op.drop_table("library_categories")

    op.drop_index("ix_library_settings_org_id", table_name="library_settings")
    op.drop_table("library_settings")
