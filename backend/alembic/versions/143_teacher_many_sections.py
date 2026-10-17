"""teacher_sections: a teacher may belong to more than one section

Was one row per teacher; now one row per (teacher, section), so a teacher can
sit in Primary and Secondary at once.

Revision ID: 143_teacher_many_sections
Revises: 142_class_area_topics
"""
from alembic import op

revision = "143_teacher_many_sections"
down_revision = "142_class_area_topics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_teacher_section_org_teacher", "teacher_sections", type_="unique")
    op.create_unique_constraint(
        "uq_teacher_section_org_teacher_section", "teacher_sections",
        ["org_id", "teacher_id", "section_id"],
    )


def downgrade() -> None:
    # Keeps one row per teacher (the earliest) so the narrower constraint can return.
    op.execute(
        "DELETE FROM teacher_sections a USING teacher_sections b "
        "WHERE a.org_id = b.org_id AND a.teacher_id = b.teacher_id "
        "AND (a.created_at, a.id) > (b.created_at, b.id)"
    )
    op.drop_constraint("uq_teacher_section_org_teacher_section", "teacher_sections", type_="unique")
    op.create_unique_constraint("uq_teacher_section_org_teacher", "teacher_sections", ["org_id", "teacher_id"])
