"""Lesson Planner Setup: categories + settings + supervisors + plan category link

Revision ID: 065_lesson_planner_setup
Revises: 064_assessment_domains
Create Date: 2026-07-14 15:00:00.000000

Additive + reversible. Backs the Lesson Planner Setup page: a category taxonomy
(optional label on a plan), a per-org settings singleton, and supervisor
assignments (who owns the Approve queue). Week Entries reuses the existing
academic_weeks table; Clone is a pure action over lesson_plans — neither needs a
schema change here.
"""
from alembic import op
import sqlalchemy as sa


revision = "065_lesson_planner_setup"
down_revision = "064_assessment_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_plan_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "name", name="uq_lesson_plan_category_org_name"),
    )
    op.create_index("ix_lesson_plan_categories_org_id", "lesson_plan_categories", ["org_id"])

    op.create_table(
        "lesson_planner_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("require_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_duration_minutes", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("allow_backdated", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_lesson_planner_settings_org"),
    )
    op.create_index("ix_lesson_planner_settings_org_id", "lesson_planner_settings", ["org_id"], unique=True)

    op.create_table(
        "lesson_plan_supervisors",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("supervisor_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["supervisor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "supervisor_id", "section_id", name="uq_lesson_plan_supervisor"),
    )
    op.create_index("ix_lesson_plan_supervisors_supervisor_id", "lesson_plan_supervisors", ["supervisor_id"])
    op.create_index("ix_lesson_plan_supervisors_section_id", "lesson_plan_supervisors", ["section_id"])
    op.create_index("ix_lesson_plan_supervisors_org_id", "lesson_plan_supervisors", ["org_id"])

    # Column + index + FK in one batch so SQLite rebuilds the table once.
    with op.batch_alter_table("lesson_plans") as batch:
        batch.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        batch.create_index("ix_lesson_plans_category_id", ["category_id"])
        batch.create_foreign_key(
            "fk_lesson_plans_category_id_lesson_plan_categories",
            "lesson_plan_categories", ["category_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("lesson_plans") as batch:
        batch.drop_constraint("fk_lesson_plans_category_id_lesson_plan_categories", type_="foreignkey")
        batch.drop_index("ix_lesson_plans_category_id")
        batch.drop_column("category_id")

    op.drop_index("ix_lesson_plan_supervisors_org_id", table_name="lesson_plan_supervisors")
    op.drop_index("ix_lesson_plan_supervisors_section_id", table_name="lesson_plan_supervisors")
    op.drop_index("ix_lesson_plan_supervisors_supervisor_id", table_name="lesson_plan_supervisors")
    op.drop_table("lesson_plan_supervisors")

    op.drop_index("ix_lesson_planner_settings_org_id", table_name="lesson_planner_settings")
    op.drop_table("lesson_planner_settings")

    op.drop_index("ix_lesson_plan_categories_org_id", table_name="lesson_plan_categories")
    op.drop_table("lesson_plan_categories")
