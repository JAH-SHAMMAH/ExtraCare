"""Tests for the unified parent fee-payment router (/payments/fees).

The happy-path card `initiate` (real hosted checkout link) and the whole parent flow
are proven by a LIVE script (session report). These lock the pieces that don't need
the network: available-providers logic, initiate validation, and invoice settlement.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from app.models.modules.finance import LedgerAccount, Invoice, JournalEntry, JournalLine
from app.models.modules.school import ParentGuardian
from app.models.payment import TenantPaymentSettings, PaymentProvider
from app.routers.fee_payments import (
    initiate, available_providers, _available_providers, _settle_invoice, InitiateFeePayment,
)
from app.config import get_settings

pytestmark = pytest.mark.asyncio


async def _receivable(db, org) -> LedgerAccount:
    a = LedgerAccount(id=str(uuid.uuid4()), code="1200", name="Accounts Receivable", type="asset", org_id=org.id)
    db.add(a)
    await db.flush()
    return a


async def _invoice(db, org, recv, *, status="posted", student_id=None, total="5000.00") -> Invoice:
    inv = Invoice(id=str(uuid.uuid4()), number=f"INV-{uuid.uuid4().hex[:6]}", customer_name="Parent",
                  status=status, total=Decimal(total), receivable_account_id=recv.id,
                  student_id=student_id, org_id=org.id)
    db.add(inv)
    await db.flush()
    return inv


async def _config(db, org, provider):
    db.add(TenantPaymentSettings(org_id=org.id, provider=provider, is_active=True, encrypted_secret_key="x"))
    await db.commit()


# ── available providers ─────────────────────────────────────────────────────────

async def test_available_providers_prefers_configured(db, org, teacher):
    await _config(db, org, PaymentProvider.FLUTTERWAVE)
    res = await available_providers(db=db, current_user=teacher)
    assert res["providers"] == ["flutterwave"]   # only what the school configured


async def test_available_providers_env_fallback_when_none(db, org, teacher, monkeypatch):
    # No per-org config → fall back to whatever the platform env has creds for.
    monkeypatch.setattr(get_settings(), "REMITA_API_KEY", "demo")
    monkeypatch.setattr(get_settings(), "PAYSTACK_SECRET_KEY", "")
    monkeypatch.setattr(get_settings(), "FLUTTERWAVE_SECRET_KEY", "")
    assert await _available_providers(db, org.id) == ["remita"]


# ── initiate validation (all before any network call) ───────────────────────────

async def test_initiate_rejects_unknown_and_remita(db, org, teacher):
    with pytest.raises(HTTPException) as e1:
        await initiate(InitiateFeePayment(invoice_id="x", provider="stripe"), db=db, current_user=teacher)
    assert e1.value.status_code == 422
    with pytest.raises(HTTPException) as e2:   # remita has its own router
        await initiate(InitiateFeePayment(invoice_id="x", provider="remita"), db=db, current_user=teacher)
    assert e2.value.status_code == 422


async def test_initiate_rejects_foreign_invoice(db, org, teacher):
    # A card provider but an invoice that isn't the parent's child → 404 (before network).
    with pytest.raises(HTTPException) as exc:
        await initiate(InitiateFeePayment(invoice_id=str(uuid.uuid4()), provider="flutterwave"), db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_initiate_rejects_unposted_invoice(db, org, teacher, student):
    # Make `teacher` a guardian of `student`, then a DRAFT invoice for that student → 409.
    db.add(ParentGuardian(id=str(uuid.uuid4()), user_id=teacher.id, student_id=student.id, org_id=org.id))
    recv = await _receivable(db, org)
    inv = await _invoice(db, org, recv, status="draft", student_id=student.id)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await initiate(InitiateFeePayment(invoice_id=inv.id, provider="flutterwave"), db=db, current_user=teacher)
    assert exc.value.status_code == 409


# ── invoice settlement (the record path) ────────────────────────────────────────

async def _entries(db, org) -> int:
    return (await db.execute(select(func.count(JournalEntry.id)).where(JournalEntry.org_id == org.id))).scalar()


async def test_settle_invoice_posts_balanced_entry_and_is_idempotent(db, org, teacher):
    recv = await _receivable(db, org)
    inv = await _invoice(db, org, recv, status="posted", total="5000.00")
    await db.commit()

    before = await _entries(db, org)
    await _settle_invoice(db, org.id, inv, Decimal("5000.00"), PaymentProvider.FLUTTERWAVE, "ec_ref", teacher, None)
    assert await _entries(db, org) == before + 1

    reloaded = (await db.execute(select(Invoice).where(Invoice.id == inv.id))).scalar_one()
    assert reloaded.status == "paid" and reloaded.payment_entry_id is not None

    lines = (await db.execute(select(JournalLine).where(JournalLine.entry_id == reloaded.payment_entry_id))).scalars().all()
    assert len(lines) == 2
    assert sum(float(l.debit) for l in lines) == sum(float(l.credit) for l in lines) == 5000.0   # balanced
    dr = next(l for l in lines if float(l.debit) > 0)
    cr = next(l for l in lines if float(l.credit) > 0)
    bank = (await db.execute(select(LedgerAccount).where(LedgerAccount.org_id == org.id, LedgerAccount.code == "1017"))).scalar_one()
    assert bank.name == "Flutterwave / Bank"
    assert dr.account_id == bank.id and cr.account_id == recv.id

    # Idempotent: settling an already-paid invoice posts nothing more.
    await _settle_invoice(db, org.id, reloaded, Decimal("5000.00"), PaymentProvider.FLUTTERWAVE, "ec_ref", teacher, None)
    assert await _entries(db, org) == before + 1
