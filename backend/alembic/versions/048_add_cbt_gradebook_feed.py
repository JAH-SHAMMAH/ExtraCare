"""CBT gradebook feed (Phase 2): Grade.cbt_exam_id + CBTExam.term

Revision ID: 048_cbt_gradebook_feed
Revises: 047_cbt_results_publish
Create Date: 2026-07-10 12:00:00.000000

Additive + reversible. Lets published CBT results feed the existing gradebook:
- grades.cbt_exam_id — a distinct FK from exam_id (which points at the manual
  `exams` table) tagging a Grade fed from a CBT sitting.
- cbt_exams.term — the term a sitting belongs to; tags fed Grade rows so the
  gradebook can scope/publish them.
Both nullable (no backfill): existing grades keep cbt_exam_id NULL; existing CBT
exams keep term NULL until an author sets one.
"""
from alembic import op
import sqlalchemy as sa


revision = "048_cbt_gradebook_feed"
down_revision = "047_cbt_results_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("grades", schema=None) as b:
        b.add_column(sa.Column("cbt_exam_id", sa.String(length=36), nullable=True))
        b.create_index(op.f("ix_grades_cbt_exam_id"), ["cbt_exam_id"], unique=False)
        b.create_foreign_key(
            op.f("fk_grades_cbt_exam_id_cbt_exams"), "cbt_exams", ["cbt_exam_id"], ["id"],
        )
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.add_column(sa.Column("term", sa.String(length=50), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cbt_exams", schema=None) as b:
        b.drop_column("term")
    with op.batch_alter_table("grades", schema=None) as b:
        b.drop_constraint(op.f("fk_grades_cbt_exam_id_cbt_exams"), type_="foreignkey")
        b.drop_index(op.f("ix_grades_cbt_exam_id"))
        b.drop_column("cbt_exam_id")
