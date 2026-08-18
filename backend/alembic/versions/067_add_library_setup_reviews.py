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
    # Defensive: library_books and library_loans were never created in migration history.
    # On fresh databases, create them before FK references. On existing databases, this is a no-op.
    from sqlalchemy import inspect
    inspector = inspect(op.get_bind())

    if "library_books" not in inspector.get_table_names():
        op.create_table(
            "library_books",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("author", sa.String(length=255), nullable=False),
            sa.Column("isbn", sa.String(length=20), nullable=True),
            sa.Column("category", sa.String(length=60), nullable=True),
            sa.Column("publisher", sa.String(length=255), nullable=True),
            sa.Column("publication_year", sa.Integer, nullable=True),
            sa.Column("cover_url", sa.String(length=500), nullable=True),
            sa.Column("shelf_location", sa.String(length=30), nullable=True),
            sa.Column("total_copies", sa.Integer, nullable=False, server_default="1"),
            sa.Column("available_copies", sa.Integer, nullable=False, server_default="1"),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("org_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_library_books_title", "library_books", ["title"])
        op.create_index("ix_library_books_isbn", "library_books", ["isbn"])
        op.create_index("ix_library_books_category", "library_books", ["category"])
        op.create_index("ix_library_books_org_id", "library_books", ["org_id"])
        op.create_index("ix_library_books_title_org", "library_books", ["title", "org_id"])

    if "library_loans" not in inspector.get_table_names():
        op.create_table(
            "library_loans",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("book_id", sa.String(length=36), nullable=False),
            sa.Column("borrower_user_id", sa.String(length=36), nullable=False),
            sa.Column("issued_by", sa.String(length=36), nullable=True),
            sa.Column("borrowed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("due_date", sa.Date, nullable=False),
            sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="borrowed"),
            sa.Column("org_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["book_id"], ["library_books.id"]),
            sa.ForeignKeyConstraint(["borrower_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_library_loans_book_id", "library_loans", ["book_id"])
        op.create_index("ix_library_loans_borrower_user_id", "library_loans", ["borrower_user_id"])
        op.create_index("ix_library_loans_due_date", "library_loans", ["due_date"])
        op.create_index("ix_library_loans_status", "library_loans", ["status"])
        op.create_index("ix_library_loans_org_id", "library_loans", ["org_id"])

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
