"""Sample picture on a domain rating (Nursery report)

Revision ID: 141_domain_rating_photo
Revises: 140_report_branding_per_section
Create Date: 2026-10-17 13:00:00.000000

Fairview's Nursery page prints a SAMPLE PICTURE beside each Early Learning Goal.
One nullable column; existing rows are unaffected.
"""
from alembic import op
import sqlalchemy as sa


revision = "141_domain_rating_photo"
down_revision = "140_report_branding_per_section"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_domain_ratings", sa.Column("photo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("student_domain_ratings", "photo_url")
