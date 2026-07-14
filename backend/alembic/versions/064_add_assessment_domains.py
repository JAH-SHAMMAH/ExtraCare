"""School Reports R3: assessment domains + student ratings

Revision ID: 064_assessment_domains
Revises: 063_subject_assessments
Create Date: 2026-07-13 13:00:00.000000

Additive + reversible. Two tables backing the criterion-referenced / non-cognitive
report layer: EYFS areas + goals (Nursery), Cambridge attainment strands (the
hybrid overlay), and Nigerian psychomotor / affective domains — plus a student's
rating against each per term.
"""
from alembic import op
import sqlalchemy as sa


revision = "064_assessment_domains"
down_revision = "063_subject_assessments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessment_domains",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=36), nullable=False),
        sa.Column("domain_type", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("parent_domain_id", sa.String(length=36), nullable=True),
        sa.Column("parent_subject_id", sa.String(length=36), nullable=True),
        sa.Column("rating_scale_id", sa.String(length=36), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["section_id"], ["school_sections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_domain_id"], ["assessment_domains.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rating_scale_id"], ["grading_scales.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assessment_domains_section_id", "assessment_domains", ["section_id"])
    op.create_index("ix_assessment_domains_parent_domain_id", "assessment_domains", ["parent_domain_id"])
    op.create_index("ix_assessment_domains_parent_subject_id", "assessment_domains", ["parent_subject_id"])
    op.create_index("ix_assessment_domains_org_section", "assessment_domains", ["org_id", "section_id"])

    op.create_table(
        "student_domain_ratings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("term", sa.String(length=50), nullable=False),
        sa.Column("domain_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.String(length=60), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["domain_id"], ["assessment_domains.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "term", "domain_id", name="uq_student_domain_rating"),
    )
    op.create_index("ix_student_domain_ratings_student_id", "student_domain_ratings", ["student_id"])
    op.create_index("ix_student_domain_ratings_domain_id", "student_domain_ratings", ["domain_id"])
    op.create_index("ix_student_domain_ratings_term", "student_domain_ratings", ["org_id", "term"])


def downgrade() -> None:
    op.drop_index("ix_student_domain_ratings_term", table_name="student_domain_ratings")
    op.drop_index("ix_student_domain_ratings_domain_id", table_name="student_domain_ratings")
    op.drop_index("ix_student_domain_ratings_student_id", table_name="student_domain_ratings")
    op.drop_table("student_domain_ratings")
    op.drop_index("ix_assessment_domains_org_section", table_name="assessment_domains")
    op.drop_index("ix_assessment_domains_parent_subject_id", table_name="assessment_domains")
    op.drop_index("ix_assessment_domains_parent_domain_id", table_name="assessment_domains")
    op.drop_index("ix_assessment_domains_section_id", table_name="assessment_domains")
    op.drop_table("assessment_domains")
