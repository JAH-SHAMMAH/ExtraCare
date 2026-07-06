"""Tests for the encryption-at-rest service (app/services/crypto.py).

Pure-unit: no DB, no network. Proves the primitive is correct BEFORE anything
stores real secrets on top of it — round-trip, authenticated-tamper detection,
wrong-key/AAD rejection, key rotation across versions, masking, and the
transparent EncryptedStr column type.
"""
from __future__ import annotations

import base64
import os

import pytest

from app.config import get_settings
from app.services import crypto
from app.services.crypto import (
    encrypt, decrypt, mask, reencrypt, needs_rotation, is_configured,
    looks_like_token, EncryptedStr, EncryptionNotConfigured, DecryptionError,
)


def _b64key(n: int = 32) -> str:
    return base64.b64encode(os.urandom(n)).decode()


@pytest.fixture
def key(monkeypatch):
    """Configure a single active v1 key for the test, then reset the key ring."""
    settings = get_settings()
    k = _b64key()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", k)
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_VERSION", 1)
    monkeypatch.setattr(settings, "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()
    yield k
    crypto.reset_keys()


# ── Core round-trip ─────────────────────────────────────────────────────────────

def test_round_trip(key):
    token = encrypt("sk_live_secret_value")
    assert token.startswith("v1:")
    assert "sk_live_secret_value" not in token       # not stored in the clear
    assert decrypt(token) == "sk_live_secret_value"
    assert is_configured() is True


def test_nonce_is_random_per_encryption(key):
    a = encrypt("same")
    b = encrypt("same")
    assert a != b                                    # different nonce each time
    assert decrypt(a) == decrypt(b) == "same"


def test_unicode_round_trip(key):
    s = "Ådé — ₦1,250 🎓"
    assert decrypt(encrypt(s)) == s


# ── Authenticated encryption: tamper / wrong key / AAD ─────────────────────────

def test_tamper_is_detected(key):
    token = encrypt("secret")
    version, nonce_b64, ct_b64 = token.split(":")
    flipped = ct_b64[:-2] + ("AA" if ct_b64[-2:] != "AA" else "BB")
    with pytest.raises(DecryptionError):
        decrypt(f"{version}:{nonce_b64}:{flipped}")


def test_wrong_key_rejected(key, monkeypatch):
    token = encrypt("secret")
    # Swap the v1 key for a different one, same version → GCM tag fails.
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", _b64key())
    crypto.reset_keys()
    with pytest.raises(DecryptionError):
        decrypt(token)


def test_aad_binding(key):
    token = encrypt("secret", aad="org-1:gateway.secret_key")
    assert decrypt(token, aad="org-1:gateway.secret_key") == "secret"
    # Wrong / missing AAD must not decrypt (can't be lifted into another context).
    with pytest.raises(DecryptionError):
        decrypt(token, aad="org-2:gateway.secret_key")
    with pytest.raises(DecryptionError):
        decrypt(token)


@pytest.mark.parametrize("bad", ["", "garbage", "v1:only-two", "x1:a:b", "v1:!!!:@@@"])
def test_malformed_tokens_rejected(key, bad):
    with pytest.raises(DecryptionError):
        decrypt(bad)


def test_looks_like_token(key):
    assert looks_like_token(encrypt("x")) is True
    assert looks_like_token("sk_live_plain") is False


# ── Configuration guards ────────────────────────────────────────────────────────

def test_not_configured_raises(monkeypatch):
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", "")
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()
    assert is_configured() is False
    with pytest.raises(EncryptionNotConfigured):
        encrypt("x")
    crypto.reset_keys()


def test_bad_key_length_rejected(monkeypatch):
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", _b64key(16))  # 128-bit, too short
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()
    with pytest.raises(EncryptionNotConfigured):
        encrypt("x")
    crypto.reset_keys()


# ── Rotation across key versions ────────────────────────────────────────────────

def test_rotation_decrypts_old_and_reencrypts(monkeypatch):
    settings = get_settings()
    key_v1 = _b64key()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", key_v1)
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_VERSION", 1)
    monkeypatch.setattr(settings, "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()

    old_token = encrypt("secret")
    assert old_token.startswith("v1:")
    assert needs_rotation(old_token) is False

    # Rotate: v2 becomes active, v1 retired (decrypt-only).
    import json
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", _b64key())
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_VERSION", 2)
    monkeypatch.setattr(settings, "ENCRYPTION_KEYS_OLD", json.dumps({"1": key_v1}))
    crypto.reset_keys()

    # Old ciphertext still decrypts under its embedded version…
    assert decrypt(old_token) == "secret"
    assert needs_rotation(old_token) is True
    # …new writes use the active version…
    fresh = encrypt("secret")
    assert fresh.startswith("v2:") and needs_rotation(fresh) is False
    # …and re-encrypt migrates old → active without changing the plaintext.
    migrated = reencrypt(old_token)
    assert migrated.startswith("v2:")
    assert decrypt(migrated) == "secret"
    assert needs_rotation(migrated) is False

    crypto.reset_keys()


# ── Masking ─────────────────────────────────────────────────────────────────────

def test_mask():
    assert mask("sk_live_1234ABCD").endswith("ABCD")
    assert set(mask("sk_live_1234ABCD")[:-4]) == {"•"}
    assert mask("abc") == "•••"          # <= visible → fully masked
    assert mask("") == ""
    assert mask(None) == ""


# ── Transparent column type ─────────────────────────────────────────────────────

def test_encrypted_str_column_round_trip(key):
    col = EncryptedStr()
    stored = col.process_bind_param("secret", None)
    assert stored is not None and looks_like_token(stored) and "secret" not in stored
    assert col.process_result_value(stored, None) == "secret"
    # None passes through untouched (nullable columns stay null).
    assert col.process_bind_param(None, None) is None
    assert col.process_result_value(None, None) is None


def test_encrypted_str_column_with_aad(key):
    bound = EncryptedStr(aad="gw.secret")
    stored = bound.process_bind_param("s", None)
    assert bound.process_result_value(stored, None) == "s"
    # A column WITHOUT the matching AAD must not read it back (context binding).
    with pytest.raises(DecryptionError):
        EncryptedStr().process_result_value(stored, None)
