"""Clubs: management tables (settings, grades, coordinators, deadlines)

Revision ID: 087_club_management
Revises: 086_pocket_money_items
Create Date: 2026-07-22 19:40:00.000000

Additive + reversible. Backs the Educare "Manage Clubs" tabs: a club settings
singleton (limit / auto-approve / term-based), the club-grade band table, the
club-coordinator assignment table, and the per-term enrolment deadline table.
"""
from alembic import op
import sqlalchemy as sa


revision = "087_club_management"
down_revision = "086_pocket_money_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "club_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("club_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("auto_approve", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("term_based_activities", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_club_settings_org"),
    )
    op.create_index("ix_club_settings_org_id", "club_settings", ["org_id"])

    op.create_table(
        "club_grades",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("grade_letter", sa.String(length=10), nullable=False),
        sa.Column("grade_point", sa.Float(), nullable=True),
        sa.Column("remarks", sa.String(length=200), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_club_grades_org_id", "club_grades", ["org_id"])

    op.create_table(
        "club_coordinators",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("coordinator_id", sa.String(length=36), nullable=False),
        sa.Column("club_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coordinator_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["club_id"], ["clubs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "coordinator_id", "club_id", name="uq_club_coordinator"),
    )
    op.create_index("ix_club_coordinators_coordinator_id", "club_coordinators", ["coordinator_id"])
    op.create_index("ix_club_coordinators_club_id", "club_coordinators", ["club_id"])
    op.create_index("ix_club_coordinators_org_id", "club_coordinators", ["org_id"])

    op.create_table(
        "club_enrollment_deadlines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column("term", sa.String(length=40), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_club_enrollment_deadlines_org_id", "club_enrollment_deadlines", ["org_id"])


def downgrade() -> None:
    op.drop_table("club_enrollment_deadlines")
    op.drop_index("ix_club_coordinators_org_id", table_name="club_coordinators")
    op.drop_index("ix_club_coordinators_club_id", table_name="club_coordinators")
    op.drop_index("ix_club_coordinators_coordinator_id", table_name="club_coordinators")
    op.drop_table("club_coordinators")
    op.drop_index("ix_club_grades_org_id", table_name="club_grades")
    op.drop_table("club_grades")
    op.drop_index("ix_club_settings_org_id", table_name="club_settings")
    op.drop_table("club_settings")
