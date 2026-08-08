"""Add section_id to period_groups and subject_groups for section-scoped setup

Revision ID: 120_add_section_id_to_timetable
Revises: 119_lesson_plan_fields_expansion
Create Date: 2026-08-08 15:45:00.000000

Allows timetable setup to be configured per school section (Early Years, Primary, Secondary).
"""
from alembic import op
import sqlalchemy as sa


revision = "120_add_section_id_to_timetable"
down_revision = "119_lesson_plan_fields_expansion"
branch_labels = None
depends_on = None


def upgrade():
    # Add section_id to period_groups (optional, nullable for backward compatibility)
    op.add_column('period_groups', sa.Column('section_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_period_groups_section_id',
        'period_groups',
        'school_sections',
        ['section_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_period_groups_section_id', 'period_groups', ['section_id'])

    # Add section_id to subject_groups (optional, nullable for backward compatibility)
    op.add_column('subject_groups', sa.Column('section_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_subject_groups_section_id',
        'subject_groups',
        'school_sections',
        ['section_id'],
        ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_subject_groups_section_id', 'subject_groups', ['section_id'])


def downgrade():
    op.drop_index('ix_subject_groups_section_id', 'subject_groups')
    op.drop_constraint('fk_subject_groups_section_id', 'subject_groups', type_='foreignkey')
    op.drop_column('subject_groups', 'section_id')

    op.drop_index('ix_period_groups_section_id', 'period_groups')
    op.drop_constraint('fk_period_groups_section_id', 'period_groups', type_='foreignkey')
    op.drop_column('period_groups', 'section_id')
