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
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": webpush.b64u(pub), "auth": webpush.b64u(auth)}}
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
