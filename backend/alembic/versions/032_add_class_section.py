"""Add section column to school_classes

Revision ID: 032_add_class_section
Revises: 031_drop_payment_gateways
Create Date: 2026-07-05 16:00:00.000000

Additive + reversible. The class-management UI has always had a `section` field
(form input + card display) but there was no backing column, so it silently
no-op'd. This adds it alongside implementing the missing GET /school/classes.
"""

from alembic import op
import sqlalchemy as sa


revision = "032_add_class_section"
down_revision = "031_drop_payment_gateways"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("school_classes", sa.Column("section", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("school_classes", "section")
