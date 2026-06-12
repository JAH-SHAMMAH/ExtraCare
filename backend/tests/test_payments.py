"""
Tests for Phase 3 Commit 4 — Paystack payments integration.

Covers:
  • PaystackProvider.initialize_transaction builds the right payload,
    converts NGN→kobo, pins org_id + target_tier in metadata, and
    surfaces Paystack errors as PaystackError.
  • Webhook HMAC-SHA512 signature validation (good, bad, empty).
  • POST /payments/initialize derives amount server-side from plan_for(),
    requires the target tier to be an upgrade, and returns the
    Paystack checkout URL.
  • GET /payments/verify/{reference} applies a tier upgrade when
    Paystack reports success AND the transaction metadata matches the
    caller's org — and refuses cross-tenant verify attempts.
  • Failed payments log an audit entry but don't upgrade the tier.
  • Webhook path re-verifies via the API (not the body) and is
    idempotent for repeat events.
  • /payments/* returns 503 when Paystack isn't wired (Noop provider).

Tests never hit the live Paystack API. We inject a stub `httpx.AsyncClient`
into the provider so every request is intercepted and assertable.
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
from app.models import (  # noqa: F401 — populate metadata before create_all
    user as _user,
    organization as _org,
    role as _role,
    audit as _audit,
    import_job as _ij,
    usage as _usage,
    notification as _notif,
)
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.audit import AuditLog, AuditAction
from app.models.organization import Organization, SubscriptionTier
from app.services import billing as billing_svc
from app.services import notifications as notif_svc
from app.services.billing import NoopBillingProvider
from app.services.paystack import PaystackError, PaystackProvider


# ── Stub httpx client ────────────────────────────────────────────────────────

class _StubClient:
    """Mimics just enough of httpx.AsyncClient for PaystackProvider tests.

    The provider calls `client.request(method, url, headers=..., json=...)`
    and later reads `resp.status_code` + `resp.json()`. We record every
    request on `.calls` for assertions and return queued `httpx.Response`
    objects in order.
    """

    def __init__(self, responses: list[httpx.Response]):
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError(f"Stub ran out of responses for {method} {url}")
        return self._responses.pop(0)

    async def aclose(self) -> None:
        return None


def _ok(data: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"status": True, "message": "ok", "data": data})


def _rejected(message: str, status_code: int = 400) -> httpx.Response:
    return httpx.Response(status_code, json={"status": False, "message": message})


# ── Unit tests: PaystackProvider ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_transaction_builds_correct_payload():
    stub = _StubClient([_ok({
        "authorization_url": "https://paystack.test/abc",
        "access_code": "ac_123",
        "reference": "ec_fixed_ref",
    })])
    prov = PaystackProvider(
        secret_key="sk_test_123",
        public_key="pk_test_456",
        callback_url="https://app.example.com/billing/callback",
        http_client=stub,
    )

    data = await prov.initialize_transaction(
        email="admin@acme.test",
        amount_ngn=5_000,
        org_id="org-acme",
        target_tier=SubscriptionTier.PRO,
        reference="ec_fixed_ref",
    )

    assert data["authorization_url"] == "https://paystack.test/abc"
    assert data["reference"] == "ec_fixed_ref"
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/transaction/initialize")
    body = call["json"]
    # NGN → kobo at the boundary, never before.
    assert body["amount"] == 500_000
    assert body["email"] == "admin@acme.test"
    assert body["reference"] == "ec_fixed_ref"
    assert body["callback_url"] == "https://app.example.com/billing/callback"
    # Metadata is how we pin tier/org to the transaction for later verify.
    assert body["metadata"] == {"org_id": "org-acme", "target_tier": "pro"}


@pytest.mark.asyncio
async def test_initialize_transaction_rejects_non_positive_amount():
    prov = PaystackProvider(secret_key="sk_test", http_client=_StubClient([]))
    with pytest.raises(PaystackError) as exc:
        await prov.initialize_transaction(
            email="a@b.test",
            amount_ngn=0,
            org_id="o",
            target_tier=SubscriptionTier.PRO,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_paystack_rejected_envelope_raises_error():
    stub = _StubClient([_rejected("Duplicate reference.", status_code=400)])
    prov = PaystackProvider(secret_key="sk_test", http_client=stub)
    with pytest.raises(PaystackError) as exc:
        await prov.initialize_transaction(
            email="a@b.test",
            amount_ngn=5_000,
            org_id="o",
            target_tier=SubscriptionTier.PRO,
        )
    assert "Duplicate reference" in exc.value.message


@pytest.mark.asyncio
async def test_verify_transaction_returns_data_envelope():
    stub = _StubClient([_ok({
        "reference": "ec_ref_1",
        "status": "success",
        "amount": 500_000,
        "metadata": {"org_id": "org-1", "target_tier": "pro"},
    })])
    prov = PaystackProvider(secret_key="sk_test", http_client=stub)

    tx = await prov.verify_transaction("ec_ref_1")

    assert tx["status"] == "success"
    assert tx["amount"] == 500_000
    assert stub.calls[0]["url"].endswith("/transaction/verify/ec_ref_1")


def test_webhook_signature_validates_correctly():
    prov = PaystackProvider(secret_key="sk_test_webhook", http_client=_StubClient([]))
    body = b'{"event":"charge.success","data":{"reference":"ec_1"}}'
    good = hmac.new(b"sk_test_webhook", body, hashlib.sha512).hexdigest()

    assert prov.webhook_signature_valid(body, good) is True
    assert prov.webhook_signature_valid(body, "0" * len(good)) is False
    assert prov.webhook_signature_valid(body, "") is False
    # Any single-byte flip must fail — guards the constant-time compare.
    flipped = good[:-1] + ("0" if good[-1] != "0" else "1")
    assert prov.webhook_signature_valid(body, flipped) is False


# ── Integration tests: routes ────────────────────────────────────────────────

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
    notif_svc.set_session_factory_override(Session)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.session_factory = Session  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.clear()
        notif_svc.set_session_factory_override(None)
        # Reset the billing provider between tests so Noop vs Paystack
        # state doesn't leak across the suite.
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
async def test_payments_initialize_happy_path(client: AsyncClient):
    _, stub = _install_paystack([_ok({
        "authorization_url": "https://paystack.test/checkout/xyz",
        "access_code": "ac_xyz",
        "reference": "ec_from_paystack",
    })])

    res = await _register(client, "pay-init")
    r = await client.post(
        "/api/v1/payments/initialize",
        headers=_auth(res["access_token"]),
        json={"target_tier": "pro"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorization_url"] == "https://paystack.test/checkout/xyz"
    assert body["reference"] == "ec_from_paystack"
    # Amount must come from plan_for(), never from the client.
    assert body["amount"] == 5_000
    assert body["target_tier"] == "pro"
    assert body["provider"] == "paystack"

    # Confirm the outbound Paystack call carried the server-derived amount
    # in kobo and the correct metadata pin.
    outbound = stub.calls[0]["json"]
    assert outbound["amount"] == 500_000
    assert outbound["metadata"]["target_tier"] == "pro"
    assert outbound["metadata"]["org_id"]  # any non-empty string

    # Audit row written.
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        rows = (await db.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.PAYMENT_INITIATED)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].resource_id == "ec_from_paystack"


@pytest.mark.asyncio
async def test_payments_initialize_rejects_non_upgrade(client: AsyncClient):
    """Enterprise org asking to downgrade to Pro must 400 rather than
    charging the customer for a plan below their current one."""
    _install_paystack([])  # no outbound call expected
    res = await _register(client, "pay-down")

    # Bump org to Enterprise directly.
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.slug == "pay-down")
        )).scalar_one()
        org.subscription_tier = SubscriptionTier.ENTERPRISE
        await db.commit()

    r = await client.post(
        "/api/v1/payments/initialize",
        headers=_auth(res["access_token"]),
        json={"target_tier": "pro"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "not_an_upgrade"


@pytest.mark.asyncio
async def test_payments_verify_applies_upgrade(client: AsyncClient):
    res = await _register(client, "pay-verify")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.slug == "pay-verify")
        )).scalar_one()
        org_id = org.id
        assert org.subscription_tier in (SubscriptionTier.FREE, None)

    _install_paystack([_ok({
        "reference": "ec_ok",
        "status": "success",
        "amount": 500_000,
        "metadata": {"org_id": org_id, "target_tier": "pro"},
    })])

    r = await client.get(
        "/api/v1/payments/verify/ec_ok",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["tier_upgraded"] is True
    assert body["target_tier"] == "pro"
    assert body["amount_ngn"] == 5_000

    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.id == org_id)
        )).scalar_one()
        assert org.subscription_tier == SubscriptionTier.PRO


@pytest.mark.asyncio
async def test_payments_verify_blocks_cross_tenant(client: AsyncClient):
    """Caller from org A cannot claim a transaction whose metadata pins
    it to org B, even if they know the reference."""
    a = await _register(client, "pay-a")
    b = await _register(client, "pay-b")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org_b = (await db.execute(
            select(Organization).where(Organization.slug == "pay-b")
        )).scalar_one()
        org_b_id = org_b.id

    _install_paystack([_ok({
        "reference": "ec_cross",
        "status": "success",
        "amount": 500_000,
        "metadata": {"org_id": org_b_id, "target_tier": "pro"},
    })])

    r = await client.get(
        "/api/v1/payments/verify/ec_cross",
        headers=_auth(a["access_token"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_payments_verify_failed_status_does_not_upgrade(client: AsyncClient):
    res = await _register(client, "pay-fail")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.slug == "pay-fail")
        )).scalar_one()
        org_id = org.id

    _install_paystack([_ok({
        "reference": "ec_bad",
        "status": "failed",
        "amount": 500_000,
        "metadata": {"org_id": org_id, "target_tier": "pro"},
    })])

    r = await client.get(
        "/api/v1/payments/verify/ec_bad",
        headers=_auth(res["access_token"]),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["tier_upgraded"] is False

    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.id == org_id)
        )).scalar_one()
        assert org.subscription_tier != SubscriptionTier.PRO
        # Failed charge leaves a PAYMENT_FAILED audit row behind.
        fail_rows = (await db.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.PAYMENT_FAILED)
        )).scalars().all()
        assert len(fail_rows) == 1


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(client: AsyncClient):
    _install_paystack([])  # no Paystack call should fire
    body = json.dumps({"event": "charge.success", "data": {"reference": "ec_1"}}).encode()
    r = await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Paystack-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_applies_upgrade_and_is_idempotent(client: AsyncClient):
    """Webhook re-verifies via the API before applying the upgrade, and
    repeat deliveries don't re-upgrade (tier_upgraded=false second time)."""
    await _register(client, "pay-hook")
    Session = client.session_factory  # type: ignore[attr-defined]
    async with Session() as db:
        org = (await db.execute(
            select(Organization).where(Organization.slug == "pay-hook")
        )).scalar_one()
        org_id = org.id

    # Two responses — one per webhook delivery. Each one re-verifies.
    _install_paystack([
        _ok({
            "reference": "ec_hook",
            "status": "success",
            "amount": 500_000,
            "metadata": {"org_id": org_id, "target_tier": "pro"},
        }),
        _ok({
            "reference": "ec_hook",
            "status": "success",
            "amount": 500_000,
            "metadata": {"org_id": org_id, "target_tier": "pro"},
        }),
    ])

    body = json.dumps({"event": "charge.success", "data": {"reference": "ec_hook"}}).encode()
    sig = hmac.new(b"sk_test_routes", body, hashlib.sha512).hexdigest()

    first = await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Paystack-Signature": sig, "Content-Type": "application/json"},
    )
    assert first.status_code == 200
    assert first.json()["tier_upgraded"] is True

    second = await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Paystack-Signature": sig, "Content-Type": "application/json"},
    )
    assert second.status_code == 200
    assert second.json()["tier_upgraded"] is False


@pytest.mark.asyncio
async def test_webhook_ignores_non_charge_events(client: AsyncClient):
    _install_paystack([])  # no verify call expected
    body = json.dumps({"event": "invoice.create", "data": {}}).encode()
    sig = hmac.new(b"sk_test_routes", body, hashlib.sha512).hexdigest()
    r = await client.post(
        "/api/v1/payments/webhook",
        content=body,
        headers={"X-Paystack-Signature": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["ignored"] == "invoice.create"


@pytest.mark.asyncio
async def test_payments_503_when_noop_provider(client: AsyncClient):
    """With no Paystack wiring, /payments/* must 503 rather than silently
    fake-succeed on the Noop provider."""
    billing_svc.set_billing_provider(NoopBillingProvider())
    res = await _register(client, "pay-noop")

    r = await client.post(
        "/api/v1/payments/initialize",
        headers=_auth(res["access_token"]),
        json={"target_tier": "pro"},
    )
    assert r.status_code == 503
    assert r.json()["detail"]["error"] == "payments_not_configured"


@pytest.mark.asyncio
async def test_payments_config_reports_configured_state(client: AsyncClient):
    _install_paystack([])
    res = await _register(client, "pay-cfg")
    r = await client.get("/api/v1/payments/config", headers=_auth(res["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "paystack"
    assert body["configured"] is True
    assert body["public_key"] == "pk_test_routes"
