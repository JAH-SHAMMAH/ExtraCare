"""optional assistant teacher per class

Revision ID: 156_class_assistants
Revises: 155_class_names_school
"""
import sqlalchemy as sa
from alembic import op

revision = "156_class_assistants"
down_revision = "155_class_names_school"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "class_assistants" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "class_assistants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("class_id", sa.String(36), sa.ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("teacher_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.UniqueConstraint("org_id", "class_id", name="uq_class_assistant"),
    )


def downgrade() -> None:
    op.drop_table("class_assistants")
