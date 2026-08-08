"""Add 12 new fields to lesson_plans table for Educare parity

Revision ID: 119_lesson_plan_fields_expansion
Revises: 118_narrow_teaching_role_scopes
Create Date: 2026-08-07 14:30:00.000000

Adds pedagogical planning fields to LessonPlan:
  - Rich text fields (TipTap + HTML): theme, sub_topic, the_hook,
    prerequisite_knowledge, rationale, methodologies, reference
  - Plain text/select: contact (VARCHAR), sex_demographics (VARCHAR)
  - Numeric: average_age (INTEGER), no_in_class (INTEGER)
  - JSON: success_criteria (TEXT, serialized JSON array of row objects)

All columns nullable (optional on lesson plan form).
Success criteria stored as JSON: {"rows": [{"id": "...", "criteria": "...",
"some": bool, "most": bool, "all": bool}, ...]}

Testing note: "reference" is NOT a Postgres reserved word (REFERENCES is,
but "reference" alone is safe). Migration tested against both SQLite and
Postgres before deployment.
"""
from alembic import op
import sqlalchemy as sa


revision = "119_lesson_plan_fields_expansion"
down_revision = "118_narrow_teaching_role_scopes"
branch_labels = None
depends_on = None


def upgrade():
    # ── Pedagogical rich-text fields ────────────────────────────────────────
    op.add_column('lesson_plans', sa.Column('theme', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('sub_topic', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('the_hook', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('prerequisite_knowledge', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('rationale', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('methodologies', sa.Text, nullable=True))
    op.add_column('lesson_plans', sa.Column('reference', sa.Text, nullable=True))

    # ── Metadata fields ────────────────────────────────────────────────────────
    op.add_column('lesson_plans', sa.Column('contact', sa.String(255), nullable=True))
    op.add_column('lesson_plans', sa.Column('sex_demographics', sa.String(100), nullable=True))
    op.add_column('lesson_plans', sa.Column('average_age', sa.Integer, nullable=True))
    op.add_column('lesson_plans', sa.Column('no_in_class', sa.Integer, nullable=True))

    # ── Success criteria (JSON) ────────────────────────────────────────────────
    op.add_column('lesson_plans', sa.Column('success_criteria', sa.Text, nullable=True))


def downgrade():
    op.drop_column('lesson_plans', 'theme')
    op.drop_column('lesson_plans', 'sub_topic')
    op.drop_column('lesson_plans', 'the_hook')
    op.drop_column('lesson_plans', 'prerequisite_knowledge')
    op.drop_column('lesson_plans', 'rationale')
    op.drop_column('lesson_plans', 'methodologies')
    op.drop_column('lesson_plans', 'reference')
    op.drop_column('lesson_plans', 'contact')
    op.drop_column('lesson_plans', 'sex_demographics')
    op.drop_column('lesson_plans', 'average_age')
    op.drop_column('lesson_plans', 'no_in_class')
    op.drop_column('lesson_plans', 'success_criteria')
