"""Tests for Payment Gateways (per-org gateway credentials, encrypted at rest).

Proves the security-critical properties:
  • secrets are ENCRYPTED AT REST — the raw DB column holds AES-GCM ciphertext,
    never the plaintext key
  • the API response NEVER carries a plaintext secret (only set/not-set booleans)
  • update rotates a secret only when a new value is supplied; omitting keeps it
  • storing a secret with NO encryption key configured fails closed (503)
  • RBAC: managing gateways is org_admin-only — a `payments:write` holder
    (accountant/manager) does NOT inherit `payment_gateways:write`
"""
from __future__ import annotations

import base64
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.services import crypto
from app.services.payment_resolver import PaymentProviderResolver, PaymentConfigError
from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.payment import TenantPaymentSettings, PaymentProvider
from app.routers.modules.finance import (
    create_payment_gateway, update_payment_gateway, delete_payment_gateway, list_payment_gateways,
)
from app.schemas.finance import PaymentGatewayCreate, PaymentGatewayUpdate


pytestmark = pytest.mark.asyncio


@pytest.fixture
def enc_key(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    monkeypatch.setattr(settings, "ENCRYPTION_KEY_VERSION", 1)
    monkeypatch.setattr(settings, "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()
    yield
    crypto.reset_keys()


async def _raw_secret(db, gid: str) -> str | None:
    """Read the raw stored secret column straight from the DB (no decrypt)."""
    return (await db.execute(text("SELECT encrypted_secret_key FROM tenant_payment_settings WHERE id = :id"), {"id": gid})).scalar()


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


# ── Encryption at rest ──────────────────────────────────────────────────────────

async def test_secret_encrypted_at_rest_and_not_leaked(db, org, teacher, enc_key):
    resp = await create_payment_gateway(
        PaymentGatewayCreate(provider="paystack", mode="test", public_key="pk_test_123",
                             secret_key="sk_test_SUPERSECRET", webhook_secret="whsec_abc"),
        request=None, db=db, current_user=teacher,
    )
    # Response exposes only set/not-set — never the plaintext.
    assert resp.secret_key_set is True and resp.webhook_secret_set is True
    dumped = resp.model_dump()
    assert "sk_test_SUPERSECRET" not in str(dumped)
    assert "secret_key" not in dumped and "webhook_secret" not in dumped

    # The raw stored column is ciphertext, not the plaintext.
    raw = await _raw_secret(db, resp.id)
    assert raw is not None
    assert "sk_test_SUPERSECRET" not in raw
    assert crypto.looks_like_token(raw)
    assert crypto.decrypt(raw) == "sk_test_SUPERSECRET"   # round-trips under the key


async def test_public_key_stored_plaintext(db, org, teacher, enc_key):
    resp = await create_payment_gateway(
        PaymentGatewayCreate(provider="remita", public_key="pk_public_ok"),
        request=None, db=db, current_user=teacher,
    )
    assert resp.public_key == "pk_public_ok"          # public keys aren't secret
    assert resp.secret_key_set is False


# ── Update: rotate vs keep ──────────────────────────────────────────────────────

async def test_update_keeps_secret_when_omitted_and_rotates_when_given(db, org, teacher, enc_key):
    g = await create_payment_gateway(
        PaymentGatewayCreate(provider="flutterwave", secret_key="sk_original"),
        request=None, db=db, current_user=teacher,
    )
    original_cipher = await _raw_secret(db, g.id)

    # Update something else, omit secret → ciphertext unchanged.
    await update_payment_gateway(g.id, PaymentGatewayUpdate(label="Main"), request=None, db=db, current_user=teacher)
    assert await _raw_secret(db, g.id) == original_cipher

    # Supply a new secret → ciphertext changes and decrypts to the new value.
    await update_payment_gateway(g.id, PaymentGatewayUpdate(secret_key="sk_rotated"), request=None, db=db, current_user=teacher)
    rotated = await _raw_secret(db, g.id)
    assert rotated != original_cipher
    assert crypto.decrypt(rotated) == "sk_rotated"


# ── Validation / guards ─────────────────────────────────────────────────────────

async def test_duplicate_provider_rejected(db, org, teacher, enc_key):
    await create_payment_gateway(PaymentGatewayCreate(provider="paystack"), request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await create_payment_gateway(PaymentGatewayCreate(provider="paystack"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_unknown_provider_and_bad_mode(db, org, teacher, enc_key):
    with pytest.raises(HTTPException) as exc:
        await create_payment_gateway(PaymentGatewayCreate(provider="stripe"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await create_payment_gateway(PaymentGatewayCreate(provider="paystack", mode="prod"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_storing_secret_without_key_fails_closed(db, org, teacher, monkeypatch):
    # No encryption key configured → storing a secret must 503, not persist plaintext.
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", "")
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEYS_OLD", "")
    crypto.reset_keys()
    assert crypto.is_configured() is False
    with pytest.raises(HTTPException) as exc:
        await create_payment_gateway(PaymentGatewayCreate(provider="paystack", secret_key="sk_x"), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 503
    # …but a gateway with NO secret (public key only) is fine without a key.
    resp = await create_payment_gateway(PaymentGatewayCreate(provider="remita", public_key="pk_ok"), request=None, db=db, current_user=teacher)
    assert resp.secret_key_set is False
    crypto.reset_keys()


# ── Lifecycle ───────────────────────────────────────────────────────────────────

async def test_list_and_soft_delete(db, org, teacher, enc_key):
    await create_payment_gateway(PaymentGatewayCreate(provider="paystack"), request=None, db=db, current_user=teacher)
    g = await create_payment_gateway(PaymentGatewayCreate(provider="remita"), request=None, db=db, current_user=teacher)
    listed = await list_payment_gateways(db=db, current_user=teacher)
    assert {x.provider for x in listed} == {"paystack", "remita"}

    await delete_payment_gateway(g.id, request=None, db=db, current_user=teacher)
    listed2 = await list_payment_gateways(db=db, current_user=teacher)
    assert {x.provider for x in listed2} == {"paystack"}


# ── RBAC: org_admin only, NOT inherited by payments:write ───────────────────────

async def test_gateway_rbac_org_admin_only(db, org):
    admin = await _preset_user(db, org, "org_admin")
    assert admin.has_permission("payment_gateways:write")
    assert admin.has_permission("payment_gateways:read")

    # The whole point of the separate namespace: payments:write does NOT satisfy it.
    for slug in ("accountant", "manager"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("payments:write")               # they CAN do finance
        assert not u.has_permission("payment_gateways:write")   # but NOT gateway secrets

    for slug in ("teacher", "parent", "cashier"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("payment_gateways:write")


# ── Consumption: the resolver actually USES the per-org secret ───────────────────

async def test_resolver_uses_per_org_decrypted_secret(db, org, teacher, enc_key):
    """The headline: a gateway configured here is what the billing resolver
    decrypts and binds the provider to — live payments use the school's own key,
    not the platform env key."""
    await create_payment_gateway(
        PaymentGatewayCreate(provider="paystack", mode="live", public_key="pk_live_x", secret_key="sk_live_PERORG"),
        request=None, db=db, current_user=teacher,
    )
    resolver = PaymentProviderResolver(get_settings())
    provider = await resolver.resolve_for_org(org.id, db)
    assert provider._secret_key == "sk_live_PERORG"   # decrypted per-org secret
    assert provider.public_key == "pk_live_x"


async def test_resolver_hard_fails_on_undecryptable_secret(db, org, teacher, enc_key, monkeypatch):
    """A stored-but-undecryptable secret (key missing/rotated) must NOT silently
    fall back to the platform account — it raises PaymentConfigError (→ hard 503 at
    the handler) so fees never route to the wrong place. Fail loud, never fail open."""
    await create_payment_gateway(
        PaymentGatewayCreate(provider="paystack", secret_key="sk_live_x"),
        request=None, db=db, current_user=teacher,
    )
    monkeypatch.setattr(get_settings(), "ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    crypto.reset_keys()
    resolver = PaymentProviderResolver(get_settings())
    with pytest.raises(PaymentConfigError):
        await resolver.resolve_for_org(org.id, db)
    crypto.reset_keys()


async def test_resolver_falls_back_when_no_per_org_secret(db, org, teacher, enc_key, monkeypatch):
    """A platform-fallback row (no secret) → resolver uses the platform env provider,
    preserving today's behaviour (proven here by setting a platform key)."""
    # Only a public key, no secret → not a real per-org credential.
    await create_payment_gateway(
        PaymentGatewayCreate(provider="paystack", public_key="pk_only"),
        request=None, db=db, current_user=teacher,
    )
    monkeypatch.setattr(get_settings(), "PAYSTACK_SECRET_KEY", "sk_PLATFORM_ENV")
    resolver = PaymentProviderResolver(get_settings())
    provider = await resolver.resolve_for_org(org.id, db)
    assert provider._secret_key == "sk_PLATFORM_ENV"   # platform env, not per-org
