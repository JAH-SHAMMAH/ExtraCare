"""Remita parent fee-payment router (NEW), prefix ``/payments/remita``.

Flow: parent sees their children's outstanding invoices → initiate (we generate
an RRR via Remita) → parent pays on Remita → Remita redirects back + sends a
webhook → we re-verify with Remita and, only if Remita confirms paid, record the
payment against the invoice through the existing ledger (Dr Cash / Cr Receivable)
and mark it paid. Recording is idempotent: the callback and webhook can fire in
any order and the invoice is paid exactly once.

NEW ENDPOINTS:
  • GET  /payments/remita/invoices          — parent's children's outstanding invoices
  • POST /payments/remita/initiate          — generate an RRR for an invoice
  • GET  /payments/remita/verify/{rrr}       — verify with Remita + record if paid
  • POST /payments/remita/webhook            — Remita notification (no auth; re-verifies)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.config import get_settings
from app.models.user import User
from app.models.modules.finance import Invoice, LedgerAccount
from app.models.modules.school import Student, ParentGuardian
from app.models.modules.remita import RemitaTransaction
from app.services import ledger
from app.services.ledger import money
from app.services import remita as remita_svc

router = APIRouter(prefix="/payments/remita", tags=["Remita Payments"])

_can_pay = Depends(PermissionChecker("payments:read"))


# ── Schemas ──────────────────────────────────────────────────────────────────────

class OutstandingInvoice(BaseModel):
    id: str
    number: str
    customer_name: str
    student_id: str | None
    student_name: str | None
    total: float
    status: str
    invoice_date: str | None


class InitiateRequest(BaseModel):
    invoice_id: str


class InitiateResponse(BaseModel):
    transaction_id: str
    order_id: str
    rrr: str | None
    amount: float
    status: str               # pending | failed
    payment_url: str | None
    message: str


class VerifyResponse(BaseModel):
    rrr: str
    status: str               # pending | paid | failed
    invoice_id: str
    amount: float
    paid_at: str | None


# ── Helpers ──────────────────────────────────────────────────────────────────────

async def _children_ids(db: AsyncSession, user: User) -> list[str]:
    rows = (await db.execute(
        select(ParentGuardian.student_id).where(
            ParentGuardian.user_id == user.id, ParentGuardian.org_id == user.org_id
        )
    )).scalars().all()
    return [r for r in rows if r]


# Fee payments land in a dedicated, clearly-named bank account so they're
# traceable and never mixed into the wrong ledger line (find-or-create, like the
# wallet float accounts).
REMITA_ACCOUNT_CODE = "1015"
REMITA_ACCOUNT_NAME = "Remita / Bank"


async def _ensure_remita_account(db: AsyncSession, org_id: str) -> LedgerAccount:
    acct = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id, LedgerAccount.code == REMITA_ACCOUNT_CODE,
            LedgerAccount.is_deleted == False,  # noqa: E712
        )
    )).scalar_one_or_none()
    if acct:
        return acct
    acct = LedgerAccount(
        code=REMITA_ACCOUNT_CODE, name=REMITA_ACCOUNT_NAME, type="asset",
        description="Fee payments received via the Remita gateway.", org_id=org_id,
    )
    db.add(acct)
    await db.flush()
    return acct


async def _record_payment(db: AsyncSession, org_id: str, tx: RemitaTransaction, actor: User | None, request: Request | None) -> None:
    """Idempotently record a confirmed Remita payment against the invoice."""
    if tx.status == "paid":
        return
    inv = (await db.execute(select(Invoice).where(Invoice.id == tx.invoice_id, Invoice.org_id == org_id))).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if not inv:
        return
    if inv.status == "paid":               # already settled by another path
        tx.status = "paid"; tx.paid_at = now
        return
    if inv.status != "posted" or not inv.receivable_account_id:
        return                              # can't settle a draft/void or one with no receivable
    cash = await _ensure_remita_account(db, org_id)
    amount = money(tx.amount)
    entry = await ledger.post_journal_entry(
        db, org_id=org_id, entry_date=now.date(),
        memo=f"Remita payment {tx.rrr} for invoice {inv.number}", source="invoice", source_id=inv.id,
        lines=[
            {"account_id": cash.id, "debit": amount, "credit": 0, "description": f"Remita {tx.rrr}"},
            {"account_id": inv.receivable_account_id, "debit": 0, "credit": amount, "description": f"Settle {inv.number}"},
        ],
        actor=actor, request=request,
    )
    inv.payment_entry_id = entry.id
    inv.status = "paid"
    tx.status = "paid"; tx.paid_at = now; tx.journal_entry_id = entry.id


# ── Endpoints ────────────────────────────────────────────────────────────────────

@router.get("/invoices", response_model=list[OutstandingInvoice], dependencies=[_can_pay])
async def my_outstanding_invoices(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    children = await _children_ids(db, current_user)
    if not children:
        return []
    names = {s.id: f"{s.first_name} {s.last_name}".strip() for s in (await db.execute(
        select(Student).where(Student.id.in_(children), Student.org_id == current_user.org_id)
    )).scalars().all()}
    invs = (await db.execute(
        select(Invoice).where(
            Invoice.org_id == current_user.org_id, Invoice.student_id.in_(children),
            Invoice.status == "posted", Invoice.is_deleted == False,  # noqa: E712
        ).order_by(Invoice.invoice_date)
    )).scalars().all()
    return [OutstandingInvoice(
        id=i.id, number=i.number, customer_name=i.customer_name, student_id=i.student_id,
        student_name=names.get(i.student_id), total=float(i.total), status=i.status,
        invoice_date=i.invoice_date.isoformat() if i.invoice_date else None,
    ) for i in invs]


@router.post("/initiate", response_model=InitiateResponse, dependencies=[_can_pay])
async def initiate(payload: InitiateRequest, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    children = await _children_ids(db, current_user)
    inv = (await db.execute(select(Invoice).where(Invoice.id == payload.invoice_id, Invoice.org_id == current_user.org_id))).scalar_one_or_none()
    if not inv or inv.student_id not in children:
        raise HTTPException(status_code=404, detail="Invoice not found for your children.")
    if inv.status != "posted":
        raise HTTPException(status_code=409, detail="This invoice is not awaiting payment.")

    order_id = f"{inv.id[:8]}-{uuid.uuid4().hex[:10]}"
    amount = float(money(inv.total))
    resp = await remita_svc.generate_rrr(
        order_id=order_id, amount=amount,
        payer_name=current_user.full_name, payer_email=current_user.email,
        description=f"School fees — invoice {inv.number}",
    )
    rrr = resp.get("RRR") or resp.get("rrr")
    tx = RemitaTransaction(
        org_id=current_user.org_id, invoice_id=inv.id, student_id=inv.student_id, order_id=order_id,
        rrr=rrr, amount=money(inv.total), status="pending" if rrr else "failed",
        payer_name=current_user.full_name, payer_email=current_user.email, raw_init=resp,
        initiated_by=current_user.id,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)

    s = get_settings()
    # ┌─ GO-LIVE CHECKLIST (1 of 2) ───────────────────────────────────────────┐
    # │ CONFIRM the hosted-redirect URL format against YOUR Remita account docs │
    # │ the moment live credentials are available. This `/remita/onepage/...`   │
    # │ path is a best-reconstruction of Remita Standard Ingestion and may      │
    # │ differ (some accounts use the inline RmPaymentEngine JS + public key,   │
    # │ or a finalize.reg form POST). The RRR is also payable on any Remita     │
    # │ channel, so a wrong URL never loses the payment — but fix this for UX.  │
    # └─────────────────────────────────────────────────────────────────────────┘
    payment_url = f"{s.REMITA_BASE_URL}/remita/onepage/{s.REMITA_MERCHANT_ID}/{rrr}/payment.spa" if rrr else None
    return InitiateResponse(
        transaction_id=tx.id, order_id=order_id, rrr=rrr, amount=amount, status=tx.status,
        payment_url=payment_url,
        message="RRR generated. Redirecting to Remita." if rrr else "Could not generate an RRR — please try again.",
    )


@router.get("/verify/{rrr}", response_model=VerifyResponse, dependencies=[_can_pay])
async def verify(rrr: str, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    tx = (await db.execute(select(RemitaTransaction).where(RemitaTransaction.rrr == rrr, RemitaTransaction.org_id == current_user.org_id))).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    status_resp = await remita_svc.query_status(rrr)
    tx.raw_status = status_resp
    if remita_svc.is_paid(status_resp):
        await _record_payment(db, current_user.org_id, tx, actor=current_user, request=request)
    await db.commit()
    await db.refresh(tx)
    return VerifyResponse(rrr=rrr, status=tx.status, invoice_id=tx.invoice_id, amount=float(tx.amount), paid_at=tx.paid_at.isoformat() if tx.paid_at else None)


@router.post("/webhook")
async def webhook(request: Request, payload: dict = Body(default={}), db: AsyncSession = Depends(get_db)):
    """Remita server-to-server notification. No auth — we re-verify with Remita
    before recording, so a spoofed call cannot mark an invoice paid."""
    rrr = payload.get("rrr") or payload.get("RRR")
    if not rrr:
        return {"received": True, "note": "no rrr in payload"}
    tx = (await db.execute(select(RemitaTransaction).where(RemitaTransaction.rrr == rrr))).scalar_one_or_none()
    if not tx:
        return {"received": True, "note": "unknown rrr"}
    status_resp = await remita_svc.query_status(rrr)
    tx.raw_status = status_resp
    if remita_svc.is_paid(status_resp):
        actor = (await db.execute(select(User).where(User.id == tx.initiated_by))).scalar_one_or_none() if tx.initiated_by else None
        await _record_payment(db, tx.org_id, tx, actor=actor, request=request)
    await db.commit()
    return {"received": True, "status": tx.status}
