"""Clubs: term-scoped membership status (Membership List / Enrollment)

Revision ID: 088_club_membership_status
Revises: 087_club_management
Create Date: 2026-07-22 20:30:00.000000

Additive + reversible. Adds status (pending/approved/withheld) plus academic_year
and term to club_memberships so enrolment can be term-scoped and approved/withheld.
"""
from alembic import op
import sqlalchemy as sa


revision = "088_club_membership_status"
down_revision = "087_club_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("club_memberships", sa.Column("status", sa.String(length=20), nullable=False, server_default="approved"))
    op.add_column("club_memberships", sa.Column("academic_year", sa.String(length=20), nullable=True))
    op.add_column("club_memberships", sa.Column("term", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("club_memberships", "term")
    op.drop_column("club_memberships", "academic_year")
    op.drop_column("club_memberships", "status")
