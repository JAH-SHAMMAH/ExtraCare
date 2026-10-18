"""Back-office modules: restaurant, procurement, livestock, rentals, fun fair, ledger, imprest, debt memo

Revision ID: 146_back_office_modules
Revises: 145_teacher_rating_anonymous
"""
import sqlalchemy as sa
from alembic import op

revision = "146_back_office_modules"
down_revision = "145_teacher_rating_anonymous"
branch_labels = None
depends_on = None


def _tables():
    from app.models.modules.office import MODELS
    return [m.__table__ for m in MODELS.values()]


def upgrade() -> None:
    bind = op.get_bind()
    for t in _tables():
        t.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for t in reversed(_tables()):
        t.drop(bind, checkfirst=True)
