"""Encryption-at-rest for stored secrets (gateway API keys).

Self-contained AES-256-GCM primitive + a transparent SQLAlchemy column type.
This module is INERT until something stores a secret — no model uses it yet.
See ENCRYPTION_SERVICE_SPEC.md for the full design and threat model.

Token format (self-describing so decrypt needs no side lookup):

    v<key_version>:<b64(nonce)>:<b64(ciphertext+tag)>

The ``v<n>`` prefix is what makes key rotation non-breaking: old ciphertext keeps
decrypting under its original key version while new writes use the active version.

Key material comes from settings (``ENCRYPTION_KEY`` = active, base64 of 32 bytes;
``ENCRYPTION_KEYS_OLD`` = retired versions kept for decrypt during rotation). The
key is SEPARATE from ``SECRET_KEY`` (JWT signing) on purpose. The production key
MUST NOT be co-located with database backups — see the config comment / spec §11-D.
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import TypeDecorator, Text

from app.config import get_settings

_NONCE_BYTES = 12          # 96-bit nonce, the AES-GCM standard
_KEY_BYTES = 32            # AES-256
_TOKEN_PREFIX = "v"


class EncryptionNotConfigured(RuntimeError):
    """Raised when encryption is requested but no active key is configured."""


class DecryptionError(ValueError):
    """Raised when a token can't be decrypted: malformed, unknown key version,
    wrong key, or tampered ciphertext (GCM tag mismatch)."""


# ── Key ring ──────────────────────────────────────────────────────────────────
# Built lazily from settings and cached. `reset_keys()` clears the cache — call
# it after rotating config or (in tests) after changing the settings key.

_keyring_cache: Optional[tuple[dict[int, bytes], int]] = None


def _decode_key(b64: str) -> bytes:
    try:
        raw = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise EncryptionNotConfigured(f"ENCRYPTION_KEY is not valid base64: {e}") from e
    if len(raw) != _KEY_BYTES:
        raise EncryptionNotConfigured(
            f"ENCRYPTION_KEY must decode to {_KEY_BYTES} bytes (got {len(raw)}). "
            'Generate: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"'
        )
    return raw


def _load_keyring() -> tuple[dict[int, bytes], int]:
    s = get_settings()
    keyring: dict[int, bytes] = {}

    old_raw = (s.ENCRYPTION_KEYS_OLD or "").strip()
    if old_raw:
        try:
            old = json.loads(old_raw)
        except json.JSONDecodeError as e:
            raise EncryptionNotConfigured(f"ENCRYPTION_KEYS_OLD is not valid JSON: {e}") from e
        for ver, b64 in old.items():
            keyring[int(ver)] = _decode_key(b64)

    active_version = int(s.ENCRYPTION_KEY_VERSION)
    if (s.ENCRYPTION_KEY or "").strip():
        keyring[active_version] = _decode_key(s.ENCRYPTION_KEY)

    return keyring, active_version


def _keyring() -> tuple[dict[int, bytes], int]:
    global _keyring_cache
    if _keyring_cache is None:
        _keyring_cache = _load_keyring()
    return _keyring_cache


def reset_keys() -> None:
    """Drop the cached key ring (after config rotation, or between tests)."""
    global _keyring_cache
    _keyring_cache = None


def is_configured() -> bool:
    """True when an active key is available to encrypt new values."""
    try:
        keyring, active = _keyring()
    except EncryptionNotConfigured:
        return False
    return active in keyring


# ── Encrypt / decrypt ─────────────────────────────────────────────────────────

def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def encrypt(plaintext: str, *, aad: str | None = None) -> str:
    """Encrypt ``plaintext`` under the ACTIVE key → a versioned token string.

    ``aad`` (additional-authenticated-data) is bound into the tag but not stored:
    the same ``aad`` must be supplied to :func:`decrypt`. Use it to pin a ciphertext
    to a context (e.g. ``f"{org_id}:gateway.secret_key"``) so it can't be lifted
    into another row and still decrypt.
    """
    keyring, active = _keyring()
    key = keyring.get(active)
    if key is None:
        raise EncryptionNotConfigured(
            "No active ENCRYPTION_KEY configured — cannot encrypt secrets."
        )
    nonce = os.urandom(_NONCE_BYTES)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"),
                             aad.encode("utf-8") if aad else None)
    return f"{_TOKEN_PREFIX}{active}:{_b64e(nonce)}:{_b64e(ct)}"


def decrypt(token: str, *, aad: str | None = None) -> str:
    """Decrypt a token produced by :func:`encrypt`. Raises :class:`DecryptionError`
    on any malformed / unknown-version / wrong-key / tampered input."""
    version, nonce, ct = _parse(token)
    keyring, _ = _keyring()
    key = keyring.get(version)
    if key is None:
        raise DecryptionError(f"No key for version {version} (rotated out or misconfigured).")
    try:
        pt = AESGCM(key).decrypt(nonce, ct, aad.encode("utf-8") if aad else None)
    except InvalidTag as e:
        raise DecryptionError("Ciphertext failed authentication (wrong key, wrong AAD, or tampered).") from e
    return pt.decode("utf-8")


def _parse(token: str) -> tuple[int, bytes, bytes]:
    if not isinstance(token, str):
        raise DecryptionError("Token must be a string.")
    parts = token.split(":")
    if len(parts) != 3 or not parts[0].startswith(_TOKEN_PREFIX):
        raise DecryptionError("Malformed token (expected 'v<n>:<nonce>:<ciphertext>').")
    try:
        version = int(parts[0][len(_TOKEN_PREFIX):])
        nonce = _b64d(parts[1])
        ct = _b64d(parts[2])
    except (ValueError, binascii.Error) as e:
        raise DecryptionError(f"Malformed token: {e}") from e
    if len(nonce) != _NONCE_BYTES:
        raise DecryptionError("Malformed token: bad nonce length.")
    return version, nonce, ct


def looks_like_token(value: str) -> bool:
    """Best-effort check that ``value`` is one of our tokens (not raw plaintext)."""
    try:
        _parse(value)
        return True
    except DecryptionError:
        return False


# ── Rotation helpers ──────────────────────────────────────────────────────────

def needs_rotation(token: str) -> bool:
    """True when ``token`` was encrypted under a non-active key version."""
    version, _, _ = _parse(token)
    _, active = _keyring()
    return version != active


def reencrypt(token: str, *, aad: str | None = None) -> str:
    """Decrypt under the embedded version, re-encrypt under the active key.
    Building block for a rotation pass over stored secrets (the table-walking
    command ships with the feature that actually stores secrets)."""
    return encrypt(decrypt(token, aad=aad), aad=aad)


# ── Masking ───────────────────────────────────────────────────────────────────

def mask(secret: str | None, visible: int = 4) -> str:
    """Human-safe display of a secret: only the last ``visible`` chars survive,
    the rest become bullets. Used for write-only fields that are never returned
    in plaintext. ``"sk_live_51H8xAbCdEf" -> "••••••••••••••CdEf"``."""
    if not secret:
        return ""
    if len(secret) <= visible:
        return "•" * len(secret)
    return "•" * (len(secret) - visible) + secret[-visible:]


# ── Transparent SQLAlchemy column type ────────────────────────────────────────

class EncryptedStr(TypeDecorator):
    """A String-like column whose value is encrypted at rest. Stores the ciphertext
    token as text; the Python attribute is plaintext ONLY in memory.

    Usage::

        secret_key = Column(EncryptedStr)                     # no context binding
        secret_key = Column(EncryptedStr(aad="gw.secret"))    # static AAD context

    Per-ROW context (e.g. binding to org_id) can't be expressed by a column type;
    for that, call :func:`encrypt`/:func:`decrypt` explicitly with a row-derived
    ``aad`` at the service layer. Reads are strict: a stored value that isn't a
    valid token raises rather than silently leaking plaintext.
    """

    impl = Text
    cache_ok = True

    def __init__(self, *args, aad: str | None = None, **kwargs):
        self._aad = aad
        super().__init__(*args, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(str(value), aad=self._aad)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value, aad=self._aad)
