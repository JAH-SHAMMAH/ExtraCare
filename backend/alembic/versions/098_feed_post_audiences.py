"""News Feed: feed_post_audiences (Publish-To role/user targeting)

Revision ID: 098_feed_post_audiences
Revises: 097_feed_post_attachments
Create Date: 2026-07-27 15:00:00.000000

Targeting for posts: no rows for a post = public (everyone in the org); a row
narrows it to a role (kind="role", ref=slug) or a user (kind="user", ref=id).
Additive — one new table, no data migration.
"""
from alembic import op
import sqlalchemy as sa


revision = "098_feed_post_audiences"
down_revision = "097_feed_post_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_post_audiences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("post_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("ref", sa.String(length=100), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["feed_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "kind", "ref", name="uq_post_audience_post_kind_ref"),
    )
    op.create_index("ix_feed_post_audiences_post_id", "feed_post_audiences", ["post_id"])
    op.create_index("ix_feed_post_audiences_org_id", "feed_post_audiences", ["org_id"])
    op.create_index("ix_feed_audience_post", "feed_post_audiences", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_feed_audience_post", table_name="feed_post_audiences")
    op.drop_index("ix_feed_post_audiences_org_id", table_name="feed_post_audiences")
    op.drop_index("ix_feed_post_audiences_post_id", table_name="feed_post_audiences")
    op.drop_table("feed_post_audiences")
