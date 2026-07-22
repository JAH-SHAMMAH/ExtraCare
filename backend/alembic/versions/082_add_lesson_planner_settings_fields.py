"""Lesson Planner Settings: Educare toggles + supervisor signature

Revision ID: 082_lesson_planner_settings
Revises: 081_voting
Create Date: 2026-07-21 14:00:00.000000

Additive + reversible. Adds the Educare "Lesson Planner Settings" fields
(display category names / change subject topic / change day format / edit lesson
plan) plus a supervisor signature image URL to lesson_planner_settings.
"""
from alembic import op
import sqlalchemy as sa


revision = "082_lesson_planner_settings"
down_revision = "081_voting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lesson_planner_settings", sa.Column("display_category_names", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("lesson_planner_settings", sa.Column("change_subject_topic", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("lesson_planner_settings", sa.Column("change_day_format", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("lesson_planner_settings", sa.Column("edit_lesson_plan", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("lesson_planner_settings", sa.Column("supervisor_signature", sa.String(length=500), nullable=True))


def downgrade() -> None:
    for col in ("supervisor_signature", "edit_lesson_plan", "change_day_format", "change_subject_topic", "display_category_names"):
        op.drop_column("lesson_planner_settings", col)
