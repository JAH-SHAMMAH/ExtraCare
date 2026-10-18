"""Back-office tables: create any missing ones and add any missing columns

Migration 146 created the tables as they were then; modules added later (and new
columns) are brought in here. Safe to run on a database that already has them.

Revision ID: 147_office_tables_sync
Revises: 146_back_office_modules
"""
import sqlalchemy as sa
from alembic import op

revision = "147_office_tables_sync"
down_revision = "146_back_office_modules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.models.modules.office import MODELS
    bind = op.get_bind()
    for m in MODELS.values():
        t = m.__table__
        t.create(bind, checkfirst=True)
        have = {c["name"] for c in sa.inspect(bind).get_columns(t.name)}
        for col in t.columns:
            if col.name not in have:
                op.add_column(t.name, sa.Column(col.name, col.type, nullable=True))


def downgrade() -> None:
    pass
