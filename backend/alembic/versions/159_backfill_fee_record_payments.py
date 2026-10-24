"""backfill fee-record paid amounts from invoices already paid

Before this, gateway / Remita / manual invoice payments never updated the
student's fee record, so Finance Broad View showed paid children as owing.
Per student: (sum of PAID invoices) - (already recorded on fee records) is applied
oldest-record-first, capped at each balance. Idempotent: a second run finds no gap.

Revision ID: 159_backfill_fee_record_payments
Revises: 158_notification_dismissals
"""
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = "159_backfill_fee_record_payments"
down_revision = "158_notification_dismissals"
branch_labels = None
depends_on = None

D = lambda v: Decimal(str(v or 0)).quantize(Decimal("0.01"))  # noqa: E731


def upgrade() -> None:
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "invoices" not in tables or "student_fee_records" not in tables:
        return
    paid = bind.execute(sa.text(
        "SELECT org_id, student_id, SUM(total) FROM invoices "
        "WHERE status='paid' AND student_id IS NOT NULL AND COALESCE(is_deleted, false)=false "
        "GROUP BY org_id, student_id")).fetchall()
    for org_id, student_id, total in paid:
        recs = bind.execute(sa.text(
            "SELECT id, total_fee, paid_amount, discount_amount FROM student_fee_records "
            "WHERE org_id=:o AND student_id=:s AND COALESCE(is_deleted, false)=false ORDER BY created_at"),
            {"o": org_id, "s": student_id}).fetchall()
        if not recs:
            continue
        left = D(total) - sum((D(r[2]) for r in recs), D(0))
        for rid, tf, pa, da in recs:
            if left <= 0:
                break
            room = D(tf) - D(pa) - D(da)
            if room <= 0:
                continue
            take = min(left, room)
            new_paid = D(pa) + take
            out = max(D(tf) - new_paid - D(da), D(0))
            bind.execute(sa.text(
                "UPDATE student_fee_records SET paid_amount=:p, outstanding_balance=:b, "
                "is_paid=:ip, payment_status=:st WHERE id=:i"),
                {"p": float(new_paid), "b": float(out), "ip": out <= 0, "st": "paid" if out <= 0 else "partial", "i": rid})
            left -= take


def downgrade() -> None:
    pass
