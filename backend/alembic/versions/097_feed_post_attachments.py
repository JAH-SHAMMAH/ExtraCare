"""News Feed: feed_post_attachments (multi-attachment: image/video/file/link)

Revision ID: 097_feed_post_attachments
Revises: 096_auditaction_enum_backfill
Create Date: 2026-07-27 12:00:00.000000

Robust attachment model so a post can carry several attachments of mixed kinds
(image / video / document / link), replacing the single media_url/media_type on
feed_posts (those columns are kept for existing posts). Additive — creates one
new table, no data migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "097_feed_post_attachments"
down_revision = "096_auditaction_enum_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_post_attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["feed_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feed_post_attachments_post_id", "feed_post_attachments", ["post_id"])
    op.create_index("ix_feed_post_attachments_org_id", "feed_post_attachments", ["org_id"])
    op.create_index("ix_feed_attachment_post", "feed_post_attachments", ["post_id", "sort_order"])


def downgrade() -> None:
    op.drop_index("ix_feed_attachment_post", table_name="feed_post_attachments")
    op.drop_index("ix_feed_post_attachments_org_id", table_name="feed_post_attachments")
    op.drop_index("ix_feed_post_attachments_post_id", table_name="feed_post_attachments")
    op.drop_table("feed_post_attachments")
