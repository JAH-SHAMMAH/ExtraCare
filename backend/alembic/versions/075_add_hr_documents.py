"""HR Documents & Templates: hr_documents

Revision ID: 075_hr_documents
Revises: 074_trainings
Create Date: 2026-07-20 16:00:00.000000

Additive + reversible. HR document/template registry pointing at uploaded files.
Matches TenantMixin — org_id is an indexed String, no FK.
"""
from alembic import op
import sqlalchemy as sa


revision = "075_hr_documents"
down_revision = "074_trainings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_documents_org_id", "hr_documents", ["org_id"])
    op.create_index("ix_hr_documents_org_category", "hr_documents", ["org_id", "category"])


def downgrade() -> None:
    op.drop_index("ix_hr_documents_org_category", table_name="hr_documents")
    op.drop_index("ix_hr_documents_org_id", table_name="hr_documents")
    op.drop_table("hr_documents")
