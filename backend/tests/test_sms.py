"""
SMS coverage — recipient phone normalisation (who actually gets messaged).

The SMS send path's RBAC (admin-only), per-org rate limiting, and audit-row
writing are exercised by test_rate_limit.py + test_audit_coverage.py + the
full-suite import. Here we lock the E.164 normaliser, which decides which
contacts are messageable and guards against sending to junk numbers.
"""

from app.services.sms import normalise_phone_e164


def test_none_and_empty_return_none():
    assert normalise_phone_e164(None) is None
    assert normalise_phone_e164("") is None


def test_junk_and_too_short_return_none():
    assert normalise_phone_e164("not-a-number") is None
    assert normalise_phone_e164("123") is None


def test_nigerian_local_trunk_becomes_e164():
    assert normalise_phone_e164("08031234567") == "+2348031234567"
    # punctuation/spacing is stripped before normalising
    assert normalise_phone_e164("0803 123 4567") == "+2348031234567"


def test_already_e164_is_preserved():
    assert normalise_phone_e164("+2348031234567") == "+2348031234567"


def test_double_zero_international_prefix():
    assert normalise_phone_e164("002348031234567") == "+2348031234567"


# ── Real gateway (Termii) ────────────────────────────────────────────────────

import uuid  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402
from app.routers.modules import sms as sms_router  # noqa: E402
from app.services import sms as sms_svc  # noqa: E402


_REAL_CLIENT = httpx.AsyncClient


def _use_transport(monkeypatch, handler):
    real = _REAL_CLIENT

    def factory(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real(*a, **kw)
    monkeypatch.setattr(httpx, "AsyncClient", factory)


def _key(monkeypatch, key="k-123"):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "TERMII_API_KEY", key)
    monkeypatch.setattr(cfg, "TERMII_CHANNEL", "generic")


@pytest.mark.asyncio
async def test_termii_send_success_records_message_id_not_delivered(monkeypatch):
    _key(monkeypatch)
    seen = {}

    def handler(req):
        seen["body"] = req.read().decode()
        return httpx.Response(200, json={"message_id": "abc123", "message": "Successfully Sent", "balance": 9})
    _use_transport(monkeypatch, handler)
    res = await sms_svc.TermiiProvider().send(to="+2348031234567", body="Hi", sender_id="FAIRVIEW")
    assert res.accepted and res.provider_message_id == "abc123" and res.delivered is False
    assert '"to":"2348031234567"' in seen["body"].replace(" ", "")   # digits only, no +
    assert '"from":"FAIRVIEW"' in seen["body"].replace(" ", "")


@pytest.mark.asyncio
async def test_termii_rejection_and_network_failure_surface_a_reason(monkeypatch):
    _key(monkeypatch)
    _use_transport(monkeypatch, lambda req: httpx.Response(400, json={"message": "ApplicationSenderId not found"}))
    bad = await sms_svc.TermiiProvider().send(to="+2348031234567", body="Hi", sender_id="NOPE")
    assert not bad.accepted and "SenderId" in bad.error_message

    def boom(req):
        raise httpx.ConnectError("down")
    _use_transport(monkeypatch, boom)
    down = await sms_svc.TermiiProvider().send(to="+2348031234567", body="Hi", sender_id="X")
    assert not down.accepted and "reach" in down.error_message


@pytest.mark.asyncio
async def test_termii_without_a_key_does_not_send_and_balance_works(monkeypatch):
    _key(monkeypatch, key="")
    p = sms_svc.TermiiProvider()
    assert p.configured is False
    assert (await p.send(to="+2348031234567", body="x", sender_id="X")).accepted is False
    _key(monkeypatch)
    _use_transport(monkeypatch, lambda req: httpx.Response(200, json={"user": "u", "balance": 1500.5, "currency": "NGN"}))
    assert await sms_svc.TermiiProvider().balance() == {"amount": 1500.5, "currency": "NGN"}


def test_unconfigured_live_gateway_is_a_clear_503(monkeypatch):
    monkeypatch.setattr(get_settings(), "SMS_PROVIDER", "termii")
    _key(monkeypatch, key="")
    with pytest.raises(HTTPException) as e:
        sms_router._live_provider()
    assert e.value.status_code == 503 and "isn't set up" in e.value.detail
    monkeypatch.setattr(get_settings(), "SMS_PROVIDER", "nonsense")
    with pytest.raises(HTTPException) as e2:
        sms_router._live_provider()
    assert e2.value.status_code == 503


@pytest.mark.asyncio
async def test_gateway_status_reports_mock_and_live(db, org, monkeypatch):
    admin = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:5]}@x.com", full_name="A",
                 status=UserStatus.ACTIVE, org_id=org.id, is_superadmin=True)
    admin.roles = []
    db.add(admin)
    await db.commit()

    class Req:  # minimal stand-in for starlette Request
        base_url = "https://api.example.com/"
    monkeypatch.setattr(get_settings(), "SMS_PROVIDER", "mock")
    st = await sms_router.gateway_status(request=Req(), db=db, current_user=admin)
    assert st["provider"] == "mock" and st["live"] is False and st["configured"] is True

    monkeypatch.setattr(get_settings(), "SMS_PROVIDER", "termii")
    _key(monkeypatch)
    _use_transport(monkeypatch, lambda req: httpx.Response(200, json={"balance": 42, "currency": "NGN"}))
    st = await sms_router.gateway_status(request=Req(), db=db, current_user=admin)
    assert st["live"] and st["balance"]["amount"] == 42
    assert st["webhook_url"] == "https://api.example.com/api/v1/sms/webhook/termii"


@pytest.mark.asyncio
async def test_webhook_requires_the_secret_when_one_is_set(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "SMS_WEBHOOK_SECRET", "s3cret")

    class Req:
        def __init__(self, headers=None, qs=None):
            self.headers, self.query_params = headers or {}, qs or {}
    with pytest.raises(HTTPException) as e:
        await sms_router.provider_webhook("termii", {"message_id": "x", "status": "delivered"}, Req(), db=db)
    assert e.value.status_code == 401
    # right secret passes the gate (message simply isn't known yet → 202)
    with pytest.raises(HTTPException) as e2:
        await sms_router.provider_webhook("termii", {"message_id": "x", "status": "delivered"},
                                          Req(headers={"x-webhook-secret": "s3cret"}), db=db)
    assert e2.value.status_code == 202
