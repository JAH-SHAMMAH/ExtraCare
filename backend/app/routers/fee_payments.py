"""Unified parent fee-payment router (provider-selectable), prefix ``/payments/fees``.

Makes the per-org gateway config actually reachable by PARENTS. The parent UX is
invoice-based (pick an outstanding invoice, pay it). This router:
  • GET  /providers          — which gateway(s) the school has configured (so the UI
                                shows only those, not a fixed list).
  • POST /initiate           — {invoice_id, provider} → hosted checkout link for a
                                Paystack/Flutterwave invoice payment (via the factory).
  • GET  /verify/{reference} — re-verify with the provider; on success settle the
                                invoice (Dr <provider> Bank / Cr Receivable, mark paid).

Remita keeps its own `/payments/remita/*` router (already live-verified); the frontend
routes Remita there and Paystack/Flutterwave here. This router is CARD/hosted-checkout
only — it drives providers the resolver factory can build.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.models.payment import (
    TenantPaymentSettings, PaymentProvider, PaymentTransaction, PaymentStatus, PaymentType,
)
from app.services import ledger
from app.services.ledger import money
from app.services.payment_resolver import get_payment_resolver, PaymentConfigError

router = APIRouter(prefix="/payments/fees", tags=["Fee Payments"])

_can_pay = Depends(PermissionChecker("payments:read"))

# Providers whose hosted checkout this router drives (built by the resolver factory).
# Remita is handled by its own router, but still SHOWN by /providers so the parent UI
# can offer it (routing to /payments/remita/*).
_CARD_PROVIDERS = {PaymentProvider.PAYSTACK, PaymentProvider.FLUTTERWAVE}

# Dedicated, clearly-named bank account per gateway so receipts are traceable.
_GATEWAY_ACCOUNTS = {
    PaymentProvider.PAYSTACK: ("1016", "Paystack / Bank"),
    PaymentProvider.FLUTTERWAVE: ("1017", "Flutterwave / Bank"),
}


async def _children_ids(db: AsyncSession, user: User) -> list[str]:
    rows = (await db.execute(
        select(ParentGuardian.student_id).where(
            ParentGuardian.user_id == user.id, ParentGuardian.org_id == user.org_id)
    )).scalars().all()
    return [r for r in rows if r]


async def _configured_providers(db: AsyncSession, org_id: str) -> set[str]:
    """Providers the school has actually configured (active, with a stored secret)."""
    rows = (await db.execute(
        select(TenantPaymentSettings.provider).where(
            TenantPaymentSettings.org_id == org_id,
            TenantPaymentSettings.is_active == True,   # noqa: E712
            TenantPaymentSettings.is_deleted == False,  # noqa: E712
            TenantPaymentSettings.encrypted_secret_key.isnot(None),
        )
    )).scalars().all()
    return {p.value if hasattr(p, "value") else str(p) for p in rows}


async def _available_providers(db: AsyncSession, org_id: str) -> list[str]:
    """Show whichever provider(s) the school configured. If none are configured yet,
    fall back to whatever the PLATFORM env has creds for (keeps the demo working)."""
    configured = await _configured_providers(db, org_id)
    if configured:
        return [p for p in ("remita", "paystack", "flutterwave") if p in configured]
    s = get_settings()
    env = []
    if s.REMITA_API_KEY:
        env.append("remita")
    if s.PAYSTACK_SECRET_KEY:
        env.append("paystack")
    if s.FLUTTERWAVE_SECRET_KEY:
        env.append("flutterwave")
    return env


async def _gateway_account(db: AsyncSession, org_id: str, provider: PaymentProvider) -> LedgerAccount:
    code, name = _GATEWAY_ACCOUNTS[provider]
    acct = (await db.execute(
        select(LedgerAccount).where(
            LedgerAccount.org_id == org_id, LedgerAccount.code == code, LedgerAccount.is_deleted == False)  # noqa: E712
    )).scalar_one_or_none()
    if acct:
        return acct
    acct = LedgerAccount(code=code, name=name, type="asset",
                         description=f"Fee payments received via the {provider.value} gateway.", org_id=org_id)
    db.add(acct)
    await db.flush()
    return acct


async def _config_row_id(db: AsyncSession, org_id: str, provider: PaymentProvider) -> str:
    """The TenantPaymentSettings id for the FK on PaymentTransaction (find-or-create a
    platform-fallback row so an env-only provider still satisfies the FK)."""
    row = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == org_id, TenantPaymentSettings.provider == provider,
            TenantPaymentSettings.is_active == True, TenantPaymentSettings.is_deleted == False)  # noqa: E712
        .order_by(TenantPaymentSettings.created_at.desc())
    )).scalars().first()
    if row:
        return row.id
    row = TenantPaymentSettings(org_id=org_id, provider=provider, is_active=True, metadata_={"platform_fallback": True})
    db.add(row)
    await db.flush()
    return row.id


async def _settle_invoice(db, org_id, inv, amount, provider, reference, actor, request) -> None:
    """Post Dr <gateway> Bank / Cr Receivable and mark the invoice paid. Idempotent."""
    if inv.status == "paid":
        return
    if inv.status != "posted" or not inv.receivable_account_id:
        return
    bank = await _gateway_account(db, org_id, provider)
    amt = money(amount)
    entry = await ledger.post_journal_entry(
        db, org_id=org_id, entry_date=datetime.now(timezone.utc).date(),
        memo=f"{provider.value} payment {reference} for invoice {inv.number}", source="invoice", source_id=inv.id,
        lines=[
            {"account_id": bank.id, "debit": amt, "credit": 0, "description": f"{provider.value} {reference}"},
            {"account_id": inv.receivable_account_id, "debit": 0, "credit": amt, "description": f"Settle {inv.number}"},
        ],
        actor=actor, request=request,
    )
    inv.payment_entry_id = entry.id
    inv.status = "paid"


# ── Schemas ────────────────────────────────────────────────────────────────────
class InitiateFeePayment(BaseModel):
    invoice_id: str
    provider: str            # paystack | flutterwave


class InitiateFeeResponse(BaseModel):
    reference: str
    provider: str
    authorization_url: str | None
    amount_ngn: float
    invoice_id: str


class VerifyFeeResponse(BaseModel):
    reference: str
    provider: str
    status: str
    invoice_id: str | None
    amount_ngn: float


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.get("/providers", dependencies=[_can_pay])
async def available_providers(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """The gateways the school has configured (or platform-env fallbacks). The parent
    UI shows a selector from this — not a fixed list."""
    return {"providers": await _available_providers(db, current_user.org_id)}


@router.post("/initiate", response_model=InitiateFeeResponse, dependencies=[_can_pay])
async def initiate(payload: InitiateFeePayment, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    try:
        provider = PaymentProvider(payload.provider)
    except ValueError:
        raise HTTPException(status_code=422, detail="Unknown provider.")
    if provider not in _CARD_PROVIDERS:
        raise HTTPException(status_code=422, detail=f"Use the {payload.provider} flow for this provider.")

    children = await _children_ids(db, current_user)
    inv = (await db.execute(select(Invoice).where(Invoice.id == payload.invoice_id, Invoice.org_id == current_user.org_id))).scalar_one_or_none()
    if not inv or inv.student_id not in children:
        raise HTTPException(status_code=404, detail="Invoice not found for your children.")
    if inv.status != "posted":
        raise HTTPException(status_code=409, detail="This invoice is not awaiting payment.")

    resolver = get_payment_resolver()
    try:
        provider_obj = await resolver.resolve_for_org(current_user.org_id, db, provider_type=provider)
    except PaymentConfigError:
        raise HTTPException(status_code=503, detail=f"{provider.value} gateway is misconfigured. Contact the school.")
    except Exception:
        raise HTTPException(status_code=503, detail=f"{provider.value} is not available. Contact the school.")

    amount_ngn = int(money(inv.total))
    try:
        init = await provider_obj.initialize_payment(
            email=current_user.email or f"parent+{current_user.id}@example.com",
            amount_ngn=amount_ngn, org_id=current_user.org_id,
            metadata={"org_id": current_user.org_id, "invoice_id": inv.id, "student_id": inv.student_id, "payment_type": "school_fees"},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Could not start the payment: {exc}")

    reference = init.get("reference")
    settings_id = await _config_row_id(db, current_user.org_id, provider)
    tx = PaymentTransaction(
        org_id=current_user.org_id, payment_settings_id=settings_id, reference=reference,
        payment_type=PaymentType.SCHOOL_FEES, status=PaymentStatus.PENDING, provider=provider,
        amount_ngn=inv.total, currency="NGN", student_id=inv.student_id, user_id=current_user.id,
        related_id=inv.id, description=f"Fees — invoice {inv.number}",
        authorization_url=init.get("authorization_url"), customer_email=current_user.email,
        metadata_={"invoice_id": inv.id}, provider_response=init.get("_raw"),
    )
    db.add(tx)
    await db.commit()
    return InitiateFeeResponse(
        reference=reference, provider=provider.value, authorization_url=init.get("authorization_url"),
        amount_ngn=float(money(inv.total)), invoice_id=inv.id,
    )


@router.get("/verify/{reference}", response_model=VerifyFeeResponse, dependencies=[_can_pay])
async def verify(reference: str, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    tx = (await db.execute(select(PaymentTransaction).where(
        PaymentTransaction.reference == reference, PaymentTransaction.org_id == current_user.org_id))).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Payment not found.")

    resolver = get_payment_resolver()
    try:
        provider_obj = await resolver.resolve_for_org(current_user.org_id, db, provider_type=tx.provider)
        verification = await provider_obj.verify_transaction(reference)
    except PaymentConfigError:
        raise HTTPException(status_code=503, detail="Gateway is misconfigured. Contact the school.")
    except Exception:
        raise HTTPException(status_code=502, detail="Payment verification failed.")

    inv = (await db.execute(select(Invoice).where(Invoice.id == tx.related_id, Invoice.org_id == current_user.org_id))).scalar_one_or_none()
    if str(verification.get("status") or "").lower() == "success":
        if inv:
            await _settle_invoice(db, current_user.org_id, inv, tx.amount_ngn, tx.provider, reference, current_user, request)
        tx.status = PaymentStatus.SUCCESSFUL
        tx.verified_at = datetime.now(timezone.utc)
        tx.provider_reference = verification.get("id") or tx.provider_reference
        tx.provider_response = verification.get("_raw") or tx.provider_response
    await db.commit()
    return VerifyFeeResponse(
        reference=reference, provider=tx.provider.value, status=tx.status.value,
        invoice_id=tx.related_id, amount_ngn=float(money(tx.amount_ngn)),
    )
