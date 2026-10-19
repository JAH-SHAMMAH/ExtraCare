"""Alerts that reach a phone outside the app: opt-in, encryption, delivery, clean-up."""
import json
import os
import struct

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.services import webpush
from tests.test_parent_report_access import _bearer, _preset_user, family  # noqa: F401

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def http(db):
    async def _g():
        yield db
    app.dependency_overrides[get_db] = _g
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


def _browser():
    """What a phone's browser would hold: a key pair and an auth secret."""
    k = ec.generate_private_key(ec.SECP256R1())
    return k, webpush._public_raw(k), os.urandom(16)


def _decrypt_as_browser(body: bytes, k, ua_pub: bytes, auth: bytes) -> bytes:
    salt, rs, idlen = body[:16], struct.unpack(">I", body[16:20])[0], body[20]
    as_pub, ct = body[21:21 + idlen], body[21 + idlen:]
    shared = k.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    prk = HKDF(hashes.SHA256(), 32, auth, b"WebPush: info\x00" + ua_pub + as_pub).derive(shared)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(prk)
    return AESGCM(cek).decrypt(nonce, ct, None).rstrip(b"\x00")[:-1]


async def test_payload_is_readable_only_by_the_phone():
    k, pub, auth = _browser()
    body = webpush.encrypt_payload(b'{"title":"Ada arrived at school"}', webpush.b64u(pub), webpush.b64u(auth))
    assert _decrypt_as_browser(body, k, pub, auth) == b'{"title":"Ada arrived at school"}'
    assert b"Ada" not in body


async def test_subscribe_send_and_forget_dead_phone(http, db, org, family, monkeypatch):  # noqa: F811
    parent = family["parent"]
    h = _bearer(parent)
    key = (await http.get("/api/v1/push/public-key", headers=h)).json()["key"]
    assert len(webpush.b64u_d(key)) == 65
    assert (await http.get("/api/v1/push/public-key", headers=h)).json()["key"] == key  # stable
    assert (await http.post("/api/v1/push/subscribe", headers=h, json={"endpoint": "http://x", "keys": {}})).status_code == 422
    k, pub, auth = _browser()
    evil = {"endpoint": "https://internal.example/x", "keys": {"p256dh": webpush.b64u(pub), "auth": webpush.b64u(auth)}}
    assert (await http.post("/api/v1/push/subscribe", headers=h, json=evil)).status_code == 422  # only real push services
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": webpush.b64u(pub), "auth": webpush.b64u(auth)}}
    assert (await http.post("/api/v1/push/subscribe", headers=h, json=sub)).status_code == 201

    sent = []
    status = {"code": 201}

    class FakeResp:
        status_code = 201

    class FakeClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, content=None, headers=None, **kw):
            sent.append((url, content, headers))
            r = FakeResp(); r.status_code = status["code"]
            return r
    import types
    monkeypatch.setattr(webpush, "httpx", types.SimpleNamespace(AsyncClient=FakeClient))

    assert (await http.post("/api/v1/push/test", headers=h)).json() == {"sent": 1}
    url, content, headers = sent[0]
    assert url == sub["endpoint"] and headers["Authorization"].startswith("vapid t=") and f"k={key}" in headers["Authorization"]
    assert json.loads(_decrypt_as_browser(content, k, pub, auth))["title"] == "Alerts are on"

    status["code"] = 410  # the phone un-subscribed: we forget it
    assert (await http.post("/api/v1/push/test", headers=h)).json() == {"sent": 0}
    assert (await http.post("/api/v1/push/test", headers=h)).json() == {"sent": 0}
    assert len(sent) == 2  # second call found nothing left to send to


async def test_parents_are_told_when_their_childs_report_is_released(http, db, org, family):  # noqa: F811
    from sqlalchemy import select
    from app.models.modules.platform import AcademicTerm
    from app.models.notification import Notification
    from app.services.report_alerts import notify_report_released
    import uuid
    t = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", org_id=org.id)
    db.add(t); await db.commit()
    n = await notify_report_released(db, org.id, family["class"].id, t.id)
    await db.commit()
    assert n == 1  # the other child in the class has no guardian linked
    rows = (await db.execute(select(Notification).where(Notification.user_id == family["parent"].id))).scalars().all()
    assert len(rows) == 1 and rows[0].title == "Mine's Autumn report is ready" and rows[0].payload["url"].endswith("/report-card")
    assert await notify_report_released(db, org.id, None) == 0


async def test_security_headers_on_api_and_risky_uploads(http):
    r = await http.get("/api/v1/push/public-key")  # refused, but headers still apply
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store" and "referrer-policy" in r.headers


async def test_uploads_ignore_a_dishonest_file_name(monkeypatch, tmp_path):
    from app.services import storage
    monkeypatch.setattr(storage, "get_settings", lambda: type("S", (), {"UPLOAD_DIR": str(tmp_path)})())
    url = storage._local_save("org1", "avatars", "evil.html", b"x", "image/png")
    assert url.endswith(".png") and "evil" not in url
    assert storage._local_save("org1", "documents", "run.exe", b"x", "application/x-msdownload").endswith(".bin")


async def test_each_person_chooses_which_alerts_they_get(http, db, org, family, monkeypatch):  # noqa: F811
    from app.services import notifications
    h = _bearer(family["parent"])
    got = (await http.get("/api/v1/push/prefs", headers=h)).json()
    assert got["values"] == {"attendance": True, "report": True, "other": True}
    assert (await http.put("/api/v1/push/prefs", headers=h, json={"values": {"bogus": True}})).status_code == 422
    r = await http.put("/api/v1/push/prefs", headers=h, json={"values": {"report": False}})
    assert r.json()["values"] == {"attendance": True, "report": False, "other": True}
    # the switch is honoured when an alert is about to be sent
    sent = []

    async def fake_send(db_, org_id, user_id, **kw):
        sent.append(kw["title"])
        return 1
    monkeypatch.setattr(webpush, "send_to_user", fake_send)
    notifications.set_session_factory_override(lambda: _Ctx(db))
    try:
        notifications._push_later(org.id, family["parent"].id, "Report ready", "x", None, "report")
        notifications._push_later(org.id, family["parent"].id, "Arrived", "x", None, "attendance")
        import asyncio
        await asyncio.sleep(0.2)
    finally:
        notifications.set_session_factory_override(None)
    assert sent == ["Arrived"]


class _Ctx:
    def __init__(self, db): self.db = db
    async def __aenter__(self): return self.db
    async def __aexit__(self, *a): return False
