"""HTTP tests for the fee-payment card webhooks (/payments/fees/webhook/*).

The card providers' full flow (initiate → real checkout link → verify) is live-proven
in the session report; this covers the security gate: the Flutterwave webhook rejects
a bad verif-hash and accepts a matching one. (Paystack's HMAC check is unit-tested in
test_fee_payments — its webhook resolves+decrypts the provider before the signature
check, which needs a configured key that the in-memory HTTP app doesn't have.)
"""
from __future__ import annotations

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import (  # noqa: F401 — populate metadata
    user as _user, organization as _org, role as _role, audit as _audit,
    import_job as _ij, usage as _usage, notification as _notif,
)
from app.models.payment import TenantPaymentSettings, PaymentProvider, PaymentTransaction, PaymentStatus


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with Session() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_db] = _get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def _register(client: AsyncClient, slug: str) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "org_name": f"{slug} corp", "org_slug": slug, "industry": "school",
        "admin_name": "Admin", "admin_email": f"admin@{slug}.example.com", "password": "StrongPass123!",
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_flutterwave_webhook_rejects_bad_signature(client: AsyncClient):
    """Security: reject (401) a verif-hash that doesn't match the org's secret hash;
    accept a matching one (re-verify may no-op without a live key, but the gate opens)."""
    await _register(client, "school-flw-hook")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(_org.Organization).where(_org.Organization.slug == "school-flw-hook"))).scalar_one()
        db.add(PaymentTransaction(
            org_id=org.id, payment_settings_id="ps_flw", reference="ec_flw_1",
            provider=PaymentProvider.FLUTTERWAVE, payment_type="school_fees",
            status=PaymentStatus.PENDING, amount_ngn=3000, related_id="inv_1",
        ))
        db.add(TenantPaymentSettings(   # raw verif-hash so no encryption key is needed in-test
            org_id=org.id, provider=PaymentProvider.FLUTTERWAVE, is_active=True,
            encrypted_webhook_secret="flw-hash-xyz",
        ))
        await db.commit()

    body = json.dumps({"event": "charge.completed", "data": {"tx_ref": "ec_flw_1", "status": "successful", "meta": {"org_id": org.id}}})
    bad = await client.post("/api/v1/payments/fees/webhook/flutterwave", content=body,
                            headers={"verif-hash": "WRONG", "Content-Type": "application/json"})
    assert bad.status_code == 401, bad.text
    good = await client.post("/api/v1/payments/fees/webhook/flutterwave", content=body,
                             headers={"verif-hash": "flw-hash-xyz", "Content-Type": "application/json"})
    assert good.status_code == 200, good.text
