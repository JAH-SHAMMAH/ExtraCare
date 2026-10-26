"""Add the enum NAMES the attendance-event models write (same Postgres drift as 160).

`attendanceeventtype` / `attendanceeventsource` were created with lower-case values,
but SQLAlchemy writes member names, so clocking a pupil in/out failed with
`invalid input value for enum attendanceeventtype: "CHECK_IN"`. Add-only, idempotent,
Postgres only. (`subscriptiontier` gets PRO for the same reason.)

Revision ID: 161_attendance_event_enum_names
Revises: 160_payment_enum_names
"""
from alembic import op

revision = "161_attendance_event_enum_names"
down_revision = "160_payment_enum_names"
branch_labels = None
depends_on = None

_TYPES = {
    "attendanceeventtype": ["CHECK_IN", "CHECK_OUT"],
    "attendanceeventsource": ["API", "IMPORT", "MANUAL", "ZKTECO"],
    "subscriptiontier": ["PRO"],
}


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        for typ, names in _TYPES.items():
            for n in names:
                op.execute(f"ALTER TYPE {typ} ADD VALUE IF NOT EXISTS '{n}'")


def downgrade() -> None:
    pass
