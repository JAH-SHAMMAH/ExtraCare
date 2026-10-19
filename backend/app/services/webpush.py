"""Web Push (RFC 8030 + RFC 8291 aes128gcm + VAPID RFC 8292), built on `cryptography` only.

The VAPID key pair is created on first use and kept with the school's settings
(private half encrypted when ENCRYPTION_KEY is set). Nothing secret lives in the repo."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import struct
import time
from urllib.parse import urlparse

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.organization import Organization
from app.models.push import PushSubscription

_logger = logging.getLogger("extracare.webpush")
KEY = "push"


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def endpoint_hash(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode()).hexdigest()


def _seal(text: str, org_id: str) -> str:
    from app.services import crypto
    return crypto.encrypt(text, aad=f"{org_id}:vapid") if crypto.is_configured() else "plain:" + text


def _open(token: str, org_id: str) -> str:
    if token.startswith("plain:"):
        return token[6:]
    from app.services import crypto
    return crypto.decrypt(token, aad=f"{org_id}:vapid")


async def get_vapid(db: AsyncSession, org_id: str) -> tuple[ec.EllipticCurvePrivateKey, str]:
    """(private key, public key as base64url) — created and stored on first call."""
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    blob = dict((org.settings or {}).get(KEY) or {})
    if not blob.get("private"):
        pk = ec.generate_private_key(ec.SECP256R1())
        raw = pk.private_numbers().private_value.to_bytes(32, "big")
        blob = {"private": _seal(b64u(raw), org_id), "public": b64u(_public_raw(pk))}
        settings = dict(org.settings or {})
        settings[KEY] = blob
        org.settings = settings
        flag_modified(org, "settings")
        await db.flush()
    raw = b64u_d(_open(blob["private"], org_id))
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1()), blob["public"]


def _public_raw(pk: ec.EllipticCurvePrivateKey) -> bytes:
    return pk.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def vapid_header(pk: ec.EllipticCurvePrivateKey, pub: str, endpoint: str, subject: str = "mailto:admin@extracare.app") -> str:
    u = urlparse(endpoint)
    head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    claims = b64u(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": subject}, separators=(",", ":")).encode())
    msg = f"{head}.{claims}".encode()
    r, s = decode_dss_signature(pk.sign(msg, ec.ECDSA(hashes.SHA256())))
    sig = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{claims}.{sig}, k={pub}"


def encrypt_payload(payload: bytes, p256dh: str, auth: str) -> bytes:
    """RFC 8291 aes128gcm body for one record."""
    ua_pub = b64u_d(p256dh)
    auth_secret = b64u_d(auth)
    as_key = ec.generate_private_key(ec.SECP256R1())
    as_pub = _public_raw(as_key)
    shared = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    prk = HKDF(hashes.SHA256(), 32, auth_secret, b"WebPush: info\x00" + ua_pub + as_pub).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(hashes.SHA256(), 16, salt, b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDF(hashes.SHA256(), 12, salt, b"Content-Encoding: nonce\x00").derive(prk)
    ct = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack(">I", 4096) + bytes([len(as_pub)]) + as_pub + ct


async def send_to_user(db: AsyncSession, org_id: str, user_id: str, *, title: str, body: str, url: str = "/dashboard/notifications") -> int:
    """Send to every device this user allowed. Returns how many accepted. Dead devices are forgotten."""
    subs = (await db.execute(select(PushSubscription).where(PushSubscription.org_id == org_id, PushSubscription.user_id == user_id))).scalars().all()
    if not subs:
        return 0
    pk, pub = await get_vapid(db, org_id)
    data = json.dumps({"title": title, "body": body, "url": url}).encode()
    ok, dead = 0, []
    async with httpx.AsyncClient(timeout=10) as client:
        for s in subs:
            try:
                r = await client.post(s.endpoint, content=encrypt_payload(data, s.p256dh, s.auth), headers={
                    "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream",
                    "TTL": "3600", "Urgency": "high", "Authorization": vapid_header(pk, pub, s.endpoint)})
                if r.status_code in (404, 410):
                    dead.append(s.id)
                elif r.status_code < 300:
                    ok += 1
                else:
                    _logger.warning("webpush status=%s", r.status_code)
            except Exception as exc:  # network trouble must never break the caller
                _logger.warning("webpush failed: %s", exc)
    if dead:
        await db.execute(delete(PushSubscription).where(PushSubscription.id.in_(dead)))
        await db.commit()
    return ok
