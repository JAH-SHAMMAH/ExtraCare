"""FlutterwaveProvider unit tests — request-building + response-mapping (stubbed
HTTP client, no network) + the verif-hash webhook check.

The real HTTP round-trip against Flutterwave's TEST API is proven separately by a
live script (see the session report); these tests lock the normalisation contract
the fee flow depends on."""
from __future__ import annotations

import pytest

from app.services.flutterwave import FlutterwaveProvider, FlutterwaveError

pytestmark = pytest.mark.asyncio


class _StubResp:
    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class _StubClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)

    async def aclose(self):
        pass


def _provider(responses):
    return FlutterwaveProvider(secret_key="FLWSECK_TEST-x", base_url="https://api.flutterwave.com",
                               callback_url="https://portal.example/callback", http_client=_StubClient(responses))


# ── initialize_payment ──────────────────────────────────────────────────────────

async def test_initialize_payment_posts_v3_payments_and_returns_link():
    stub = _StubClient([_StubResp(200, {"status": "success", "data": {"link": "https://checkout.flutterwave.com/pay/abc"}})])
    prov = FlutterwaveProvider(secret_key="FLWSECK_TEST-x", callback_url="https://portal.example/cb", http_client=stub)
    out = await prov.initialize_payment(email="p@example.com", amount_ngn=5000, org_id="org-1",
                                        metadata={"org_id": "org-1", "student_id": "s1"})
    assert out["authorization_url"] == "https://checkout.flutterwave.com/pay/abc"
    assert out["reference"].startswith("ec_")
    call = stub.calls[0]
    assert call["method"] == "POST" and call["url"].endswith("/v3/payments")
    body = call["json"]
    assert body["currency"] == "NGN" and body["amount"] == "5000"
    assert body["customer"]["email"] == "p@example.com"
    assert body["meta"]["org_id"] == "org-1"
    assert body["redirect_url"] == "https://portal.example/cb"
    assert body["tx_ref"] == out["reference"]


async def test_initialize_rejects_nonpositive_amount():
    prov = _provider([])
    with pytest.raises(FlutterwaveError):
        await prov.initialize_payment(email="p@example.com", amount_ngn=0, org_id="o")


async def test_initialize_raises_without_link():
    prov = _provider([_StubResp(200, {"status": "success", "data": {}})])
    with pytest.raises(FlutterwaveError):
        await prov.initialize_payment(email="p@example.com", amount_ngn=100, org_id="o")


# ── verify_transaction (normalisation) ──────────────────────────────────────────

async def test_verify_maps_successful_to_success():
    prov = _provider([_StubResp(200, {"status": "success", "data": {
        "status": "successful", "id": 99, "amount": 5000, "currency": "NGN",
        "flw_ref": "FLW-REF-1", "meta": {"org_id": "org-1", "student_id": "s1"},
    }})])
    v = await prov.verify_transaction("ec_abc")
    assert v["status"] == "success"        # Flutterwave "successful" -> "success"
    assert v["id"] == 99 and v["amount"] == 5000
    assert v["metadata"] == {"org_id": "org-1", "student_id": "s1"}
    assert v["flw_ref"] == "FLW-REF-1"


async def test_verify_non_successful_status_passthrough():
    prov = _provider([_StubResp(200, {"status": "success", "data": {"status": "failed", "id": 1, "meta": {}}})])
    v = await prov.verify_transaction("ec_abc")
    assert v["status"] == "failed"


async def test_verify_no_transaction_raises():
    # Flutterwave returns an error envelope for an unpaid/unknown tx_ref.
    prov = _provider([_StubResp(200, {"status": "error", "message": "No transaction was found for this id"})])
    with pytest.raises(FlutterwaveError):
        await prov.verify_transaction("ec_unpaid")


async def test_verify_requires_reference():
    prov = _provider([])
    with pytest.raises(FlutterwaveError):
        await prov.verify_transaction("  ")


# ── webhook verif-hash ──────────────────────────────────────────────────────────

def test_webhook_signature_valid():
    assert FlutterwaveProvider.webhook_signature_valid("secret-hash-123", "secret-hash-123") is True
    assert FlutterwaveProvider.webhook_signature_valid("wrong", "secret-hash-123") is False
    assert FlutterwaveProvider.webhook_signature_valid(None, "secret-hash-123") is False
    assert FlutterwaveProvider.webhook_signature_valid("secret-hash-123", "") is False


# ── 5xx handling ────────────────────────────────────────────────────────────────

async def test_server_error_raises():
    prov = _provider([_StubResp(503, {})])
    with pytest.raises(FlutterwaveError):
        await prov.verify_transaction("ec_abc")
