"""class_area_topics: the topics a Nursery class covered in each area of learning

Revision ID: 142_class_area_topics
Revises: 141_one_current_session
"""
from alembic import op
import sqlalchemy as sa

revision = "142_class_area_topics"
down_revision = "141_one_current_session"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "class_area_topics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False, index=True),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("domain_id", sa.String(36), sa.ForeignKey("assessment_domains.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("topics", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("class_id", "term_id", "domain_id", name="uq_class_area_topic"),
    )


def downgrade() -> None:
    op.drop_table("class_area_topics")
