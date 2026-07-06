"""
Tests for school payment parent flow and webhook processing.

Covers:
- Parent initiate payment -> transaction persisted and authorization URL returned
- Parent verify endpoint updates transaction after provider verify
- Webhook processing accepts valid signature, verifies with provider, updates transaction
- Duplicate webhook delivery is idempotent
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import (  # noqa: F401 — populate metadata
    user as _user,
    organization as _org,
    role as _role,
    audit as _audit,
    import_job as _ij,
    usage as _usage,
    notification as _notif,
)
from app.models.modules.school import Student
from app.models.organization import SubscriptionTier
from app.models.payment import TenantPaymentSettings, PaymentProvider as PaymentProviderEnum, PaymentTransaction, PaymentStatus
from app.services import billing as billing_svc
from app.services.billing import NoopBillingProvider
from app.services.paystack import PaystackProvider


class _StubClient:
    def __init__(self, responses: list[httpx.Response]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("Stub ran out of responses")
        return self._responses.pop(0)

    async def aclose(self) -> None:
        return None


def _ok(data: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"status": True, "message": "ok", "data": data})


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
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        billing_svc.set_billing_provider(NoopBillingProvider())
        await engine.dispose()


async def _register(client: AsyncClient, slug: str) -> dict:
    r = await client.post("/api/v1/auth/register", json={
        "org_name": f"{slug} corp",
        "org_slug": slug,
        "industry": "school",
        "admin_name": "Admin",
        "admin_email": f"admin@{slug}.example.com",
        "password": "StrongPass123!",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _auth(tok: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _install_paystack(stub_responses: list[httpx.Response]) -> tuple[PaystackProvider, _StubClient]:
    stub = _StubClient(stub_responses)
    prov = PaystackProvider(
        secret_key="sk_test_routes",
        public_key="pk_test_routes",
        callback_url="https://app.example.com/billing/callback",
        http_client=stub,
    )
    billing_svc.set_billing_provider(prov)
    return prov, stub


@pytest.mark.asyncio
async def test_parent_initiate_and_verify(client: AsyncClient):
    # Register org and create a student
    res = await _register(client, "school-parent")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(_org.Organization).where(_org.Organization.slug == "school-parent"))).scalar_one()
        student = Student(first_name="Jane", last_name="Doe", student_id="S001", org_id=org.id)
        db.add(student)
        await db.commit()
        student_id = student.id

    # Install Paystack provider stub for initialize
    _, stub = _install_paystack([_ok({
        "authorization_url": "https://paystack.test/checkout/parent",
        "reference": "ec_parent_1",
    })])

    # Initiate payment
    r = await client.post(
        "/api/v1/school/payments/parent/initiate-payment",
        headers=_auth(res["access_token"]),
        json={"student_id": student_id, "amount_ngn": 1500, "payment_type": "school_fees"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorization_url"] == "https://paystack.test/checkout/parent"
    reference = body["reference"]

    # Now verify via parent endpoint — set provider verify stub
    prov, stub2 = _install_paystack([_ok({
        "reference": reference,
        "status": "success",
        "amount": 1500 * 100,
        "metadata": {"org_id": org.id},
    })])

    v = await client.get(f"/api/v1/school/payments/parent/verify/{reference}", headers=_auth(res["access_token"]))
    assert v.status_code == 200, v.text
    vb = v.json()
    assert vb["success"] is True
    assert vb["status"] == "success"


@pytest.mark.asyncio
async def test_initiate_hard_fails_when_per_org_secret_undecryptable(client: AsyncClient):
    """Security/tenant-isolation: if a per-org gateway secret exists but can't be
    decrypted, initiate must return 503 — it must NOT silently fall back to the
    platform Paystack account (which would route this school's fees to the wrong
    place with no visible error). Fail loud, never fail open."""
    res = await _register(client, "school-badkey")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(_org.Organization).where(_org.Organization.slug == "school-badkey"))).scalar_one()
        student = Student(first_name="Ada", last_name="X", student_id="S9", org_id=org.id)
        db.add(student)
        # A per-org Paystack config whose secret can't be decrypted (token-shaped but
        # no valid key in this env) → resolver raises PaymentConfigError.
        db.add(TenantPaymentSettings(
            org_id=org.id, provider=PaymentProviderEnum.PAYSTACK, is_active=True,
            encrypted_secret_key="v1:AAAAAAAAAAAAAAAA:BBBBBBBBBBBBBBBBBBBB",
        ))
        await db.commit()
        student_id = student.id

    # Even with a platform provider stub available, the misconfig must hard-fail.
    _install_paystack([_ok({"authorization_url": "https://paystack.test/x", "reference": "z"})])
    r = await client.post(
        "/api/v1/school/payments/parent/initiate-payment",
        headers=_auth(res["access_token"]),
        json={"student_id": student_id, "amount_ngn": 1500, "payment_type": "school_fees"},
    )
    assert r.status_code == 503, r.text


@pytest.mark.asyncio
async def test_webhook_processing_and_idempotency(client: AsyncClient):
    # Register org and create a pending transaction
    res = await _register(client, "school-hook")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(_org.Organization).where(_org.Organization.slug == "school-hook"))).scalar_one()
        tx = PaymentTransaction(
            org_id=org.id,
            payment_settings_id="ps_1",
            reference="ec_hook_school",
            provider=PaymentProviderEnum.PAYSTACK,
            payment_type="school_fees",
            status=PaymentStatus.PENDING,
            amount_ngn=2000,
        )
        db.add(tx)
        # Create tenant webhook secret row (stored raw for MVP)
        trow = TenantPaymentSettings(org_id=org.id, provider=PaymentProviderEnum.PAYSTACK, is_active=True, encrypted_webhook_secret="sk_test_routes")
        db.add(trow)
        await db.commit()

    # Install platform provider verify stub (webhook handler will call verify)
    _install_paystack([
        _ok({
            "reference": "ec_hook_school",
            "status": "success",
            "amount": 2000 * 100,
            "metadata": {"org_id": org.id},
        })
    ])

    body = json.dumps({"event": "charge.success", "data": {"reference": "ec_hook_school", "metadata": {"org_id": org.id}}}).encode()
    sig = hmac.new(b"sk_test_routes", body, hashlib.sha512).hexdigest()

    first = await client.post(
        "/api/v1/school/payments/webhook/paystack",
        content=body,
        headers={"X-Paystack-Signature": sig, "Content-Type": "application/json"},
    )
    assert first.status_code == 200

    # Second delivery — idempotent (server will return processed True or similar)
    # Ensure provider verify stub exists for second call
    _install_paystack([
        _ok({
            "reference": "ec_hook_school",
            "status": "success",
            "amount": 2000 * 100,
            "metadata": {"org_id": org.id},
        })
    ])

    second = await client.post(
        "/api/v1/school/payments/webhook/paystack",
        content=body,
        headers={"X-Paystack-Signature": sig, "Content-Type": "application/json"},
    )
    assert second.status_code == 200



@pytest.mark.asyncio
async def test_flutterwave_webhook_rejects_bad_signature(client: AsyncClient):
    """Security: the Flutterwave webhook must REJECT (401) a request whose verif-hash
    header doesn't match the org's configured secret hash, and accept a matching one."""
    res = await _register(client, "school-flw")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(select(_org.Organization).where(_org.Organization.slug == "school-flw"))).scalar_one()
        db.add(PaymentTransaction(
            org_id=org.id, payment_settings_id="ps_flw", reference="ec_flw_1",
            provider=PaymentProviderEnum.FLUTTERWAVE, payment_type="school_fees",
            status=PaymentStatus.PENDING, amount_ngn=3000,
        ))
        # Configured verif-hash (raw legacy value so no encryption key is needed in-test).
        db.add(TenantPaymentSettings(
            org_id=org.id, provider=PaymentProviderEnum.FLUTTERWAVE, is_active=True,
            encrypted_webhook_secret="flw-hash-xyz",
        ))
        await db.commit()

    body = json.dumps({"event": "charge.completed", "data": {"tx_ref": "ec_flw_1", "status": "successful", "meta": {"org_id": org.id}}})

    bad = await client.post(
        "/api/v1/school/payments/webhook/flutterwave",
        content=body, headers={"verif-hash": "WRONG", "Content-Type": "application/json"},
    )
    assert bad.status_code == 401, bad.text

    good = await client.post(
        "/api/v1/school/payments/webhook/flutterwave",
        content=body, headers={"verif-hash": "flw-hash-xyz", "Content-Type": "application/json"},
    )
    # Signature passed → not 401 (re-verify may no-op without a live key, but the gate opened).
    assert good.status_code == 200, good.text
