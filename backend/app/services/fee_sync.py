"""Keep the student's fee record (what Finance Broad View reads) in step with
invoice payments (what gateways, Remita and cashiers settle).

Fee Assignment creates a ``StudentFeeRecord``; the money arrives against an
``Invoice``. Without this bridge a parent could pay in full and the Broad View
(paid / debt / part-payment cards, students ledger) would still show the child as
owing. Applied to the child's oldest record that still has a balance, capped at
that balance, so a stray extra payment can never push ``paid`` above ``total``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import StudentFeeRecord
from app.services.ledger import money


async def apply_payment_to_fee_record(db: AsyncSession, org_id: str, student_id: str | None, amount) -> None:
    if not student_id:
        return
    left = money(amount)
    if left <= 0:
        return
    recs = (await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.org_id == org_id, StudentFeeRecord.student_id == student_id,
            StudentFeeRecord.is_deleted == False,  # noqa: E712
            StudentFeeRecord.outstanding_balance > 0)
        .order_by(StudentFeeRecord.created_at.asc())
    )).scalars().all()
    for fr in recs:
        if left <= 0:
            break
        room = money(fr.outstanding_balance)
        take = min(left, room)
        fr.paid_amount = money(money(fr.paid_amount or 0) + take)
        out = money(money(fr.total_fee or 0) - money(fr.paid_amount) - money(fr.discount_amount or 0))
        fr.outstanding_balance = out if out > 0 else money(0)
        if fr.outstanding_balance <= 0:
            fr.is_paid, fr.payment_status = True, "paid"
        else:
            fr.is_paid, fr.payment_status = False, "partial"
        left -= take
    await db.flush()
