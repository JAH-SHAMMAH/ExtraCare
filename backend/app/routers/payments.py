"""
Payments — Paystack integration.

Flow:
  1. Frontend calls POST /payments/initialize with the requested tier.
     Server looks up the plan price, builds a Paystack init payload,
     stores metadata (org_id, target_tier), and returns the hosted
     checkout URL.
  2. User completes payment on Paystack.
  3. Paystack redirects to PAYSTACK_CALLBACK_URL?reference=... and/or
     POSTs /payments/webhook.
  4. Frontend calls GET /payments/verify/{reference} — we hit
     Paystack's verify API, confirm status=success, match metadata
     against the org, and bump `subscription_tier`.

Security stance:
  • Amounts are derived from `plan_for(target_tier)` server-side.
  • Verify is always fetched fresh from Paystack; we never trust the
    redirect query string alone.
  • The webhook requires a valid HMAC-SHA512 signature.
  • Upgrades only apply if the verified metadata.org_id matches the
    caller's org_id and the tier is an upgrade over the current plan.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.plans import plan_for, suggested_upgrade_tier
from app.database import get_db
from app.deps import get_current_active_user
from app.models.audit import AuditAction
from app.models.notification import TYPE_SYSTEM
from app.models.organization import Organization, SubscriptionTier
from app.models.user import User
from app.services import notifications as notif_svc
from app.services.audit_service import log_action
from app.services.billing import get_billing_provider
from app.services.paystack import PaystackError, PaystackProvider


_logger = logging.getLogger("extracare.payments")


router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class InitializeRequest(BaseModel):
    target_tier: SubscriptionTier
    # Email is optional — defaults to the caller's account email. We keep
    # it overridable so finance can pay on behalf of an org using a
    # different receipt address if needed.
    email: EmailStr | None = None


class InitializeResponse(BaseModel):
    authorization_url: str
    reference: str
    amount: int = Field(description="Amount charged, in NGN.")
    target_tier: str
    provider: str


class VerifyResponse(BaseModel):
    success: bool
    reference: str
    status: str
    amount_ngn: int | None = None
    org_id: str
    target_tier: str
    tier_upgraded: bool
    message: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_paystack() -> PaystackProvider:
    """Resolve the active billing provider and assert it's Paystack.

    We fall back to the Noop provider in dev when PAYSTACK_SECRET_KEY is
    unset — trying to charge on Noop would silently succeed, which is
    the exact footgun we want to avoid. So /payments/* returns 503 when
    Paystack isn't wired, rather than fake success.
    """
    provider = get_billing_provider()
    if not isinstance(provider, PaystackProvider):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "payments_not_configured",
                "message": "Paystack is not configured. Set PAYSTACK_SECRET_KEY.",
            },
        )
    return provider


async def _load_org(db: AsyncSession, org_id: str) -> Organization:
    org = (await db.execute(
        select(Organization).where(Organization.id == org_id)
    )).scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return org


def _is_upgrade(current: SubscriptionTier | None, target: SubscriptionTier) -> bool:
    """True iff `target` is strictly higher than `current` in the
    upgrade path. Free < Pro < Enterprise; legacy tiers map onto the
    nearest equivalent (see core/plans._UPGRADE_PATH)."""
    order = {
        SubscriptionTier.FREE: 0,
        SubscriptionTier.STARTER: 1,
        SubscriptionTier.PRO: 2,
        SubscriptionTier.GROWTH: 3,
        SubscriptionTier.ENTERPRISE: 4,
    }
    return order.get(target, -1) > order.get(current, -1)


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post(
    "/initialize",
    response_model=InitializeResponse,
    summary="Create a Paystack checkout session for a subscription upgrade",
)
async def initialize_payment(
    body: InitializeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    provider = _require_paystack()
    org = await _load_org(db, current_user.org_id)

    if not _is_upgrade(org.subscription_tier, body.target_tier):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "not_an_upgrade",
                "message": (
                    f"Target tier {body.target_tier.value!r} is not above "
                    f"current tier {(org.subscription_tier or SubscriptionTier.FREE).value!r}."
                ),
                "suggested_tier": suggested_upgrade_tier(
                    org.subscription_tier or SubscriptionTier.FREE
                ).value,
            },
        )

    plan = plan_for(body.target_tier)
    if plan.monthly_price_ngn <= 0:
        raise HTTPException(
            status_code=400,
            detail="Selected plan has no configured price.",
        )

    email = body.email or current_user.email
    try:
        data = await provider.initialize_transaction(
            email=email,
            amount_ngn=plan.monthly_price_ngn,
            org_id=org.id,
            target_tier=body.target_tier,
        )
    except PaystackError as exc:
        _logger.warning("paystack init failed: %s", exc.message)
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    authorization_url = data.get("authorization_url")
    reference = data.get("reference")
    if not authorization_url or not reference:
        raise HTTPException(
            status_code=502,
            detail="Paystack response missing authorization_url or reference.",
        )

    await log_action(
        db,
        action=AuditAction.PAYMENT_INITIATED,
        org_id=org.id,
        actor=current_user,
        resource_type="Subscription",
        resource_id=reference,
        resource_label=body.target_tier.value,
        metadata={"amount_ngn": plan.monthly_price_ngn, "reference": reference},
        request=request,
    )
    await db.commit()

    return InitializeResponse(
        authorization_url=authorization_url,
        reference=reference,
        amount=plan.monthly_price_ngn,
        target_tier=body.target_tier.value,
        provider=provider.name,
    )


@router.get(
    "/verify/{reference}",
    response_model=VerifyResponse,
    summary="Verify a Paystack transaction and apply any resulting upgrade",
)
async def verify_payment(
    reference: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    provider = _require_paystack()
    try:
        tx = await provider.verify_transaction(reference)
    except PaystackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    return await _apply_verification(
        db, tx, request=request, actor=current_user,
        expected_org_id=current_user.org_id,
    )


@router.post(
    "/webhook",
    summary="Paystack webhook — idempotent application of verified charges",
    include_in_schema=False,
)
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paystack_signature: str = Header(default=""),
):
    """Paystack POSTs event payloads here. We verify the HMAC-SHA512
    signature, then re-call /transaction/verify to get a trusted copy of
    the transaction (avoiding any risk of body tampering) before applying
    the upgrade. Idempotent: a repeat event with an already-upgraded org
    returns 200 with tier_upgraded=false."""
    provider = _require_paystack()
    raw = await request.body()
    if not provider.webhook_signature_valid(raw, x_paystack_signature):
        _logger.warning("paystack webhook rejected: bad signature")
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        import json
        event = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    if event.get("event") != "charge.success":
        # We only act on successful charges. Other events are logged
        # and ack'd so Paystack doesn't keep retrying.
        return {"ok": True, "ignored": event.get("event")}

    reference = (event.get("data") or {}).get("reference")
    if not reference:
        raise HTTPException(status_code=400, detail="Missing reference.")

    try:
        tx = await provider.verify_transaction(reference)
    except PaystackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    result = await _apply_verification(
        db, tx, request=request, actor=None, expected_org_id=None,
    )
    return result.model_dump()


# ── Shared verification path ────────────────────────────────────────────────

async def _apply_verification(
    db: AsyncSession,
    tx: dict[str, Any],
    *,
    request: Request,
    actor: User | None,
    expected_org_id: str | None,
) -> VerifyResponse:
    """Validate a verified Paystack transaction and apply the upgrade.

    Callable from both the user-facing verify endpoint and the webhook,
    so the single source of truth for "did this charge upgrade this
    org?" lives here.
    """
    reference = tx.get("reference") or ""
    tx_status = (tx.get("status") or "").lower()
    metadata = tx.get("metadata") or {}
    # Paystack sometimes returns metadata as a stringified JSON blob
    # (older dashboards did this). Handle both shapes.
    if isinstance(metadata, str):
        import json
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    meta_org_id = metadata.get("org_id")
    meta_target = metadata.get("target_tier")

    if not meta_org_id or not meta_target:
        raise HTTPException(
            status_code=400,
            detail="Transaction metadata is missing org_id or target_tier.",
        )

    # User-facing verify must stay inside the caller's tenant — no
    # cross-tenant verify probes. Webhook passes expected_org_id=None.
    if expected_org_id is not None and expected_org_id != meta_org_id:
        raise HTTPException(
            status_code=403,
            detail="Transaction does not belong to your organization.",
        )

    org = await _load_org(db, meta_org_id)

    if tx_status != "success":
        await log_action(
            db,
            action=AuditAction.PAYMENT_FAILED,
            org_id=org.id,
            actor=actor,
            resource_type="Subscription",
            resource_id=reference,
            metadata={"paystack_status": tx_status},
            request=request,
        )
        await db.commit()
        return VerifyResponse(
            success=False,
            reference=reference,
            status=tx_status,
            amount_ngn=(tx.get("amount") or 0) // 100,
            org_id=org.id,
            target_tier=meta_target,
            tier_upgraded=False,
            message="Payment was not successful.",
        )

    try:
        target_tier = SubscriptionTier(meta_target)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown target tier in metadata: {meta_target!r}",
        )

    tier_upgraded = False
    if _is_upgrade(org.subscription_tier, target_tier):
        prior = org.subscription_tier.value if org.subscription_tier else None
        org.subscription_tier = target_tier
        tier_upgraded = True
        await log_action(
            db,
            action=AuditAction.SUBSCRIPTION_UPGRADED,
            org_id=org.id,
            actor=actor,
            resource_type="Organization",
            resource_id=org.id,
            old_values={"subscription_tier": prior},
            new_values={"subscription_tier": target_tier.value},
            metadata={"reference": reference},
            request=request,
        )
        # Nudge the org so admins see the upgrade in their inbox. Uses
        # the request-scoped session — commit happens below.
        await notif_svc.notify(
            org_id=org.id,
            user_id=None,
            type=TYPE_SYSTEM,
            title=f"Plan upgraded to {target_tier.value}",
            message=(
                f"Payment confirmed. Your plan is now "
                f"{target_tier.value.title()}."
            ),
            payload={"reference": reference, "prior_tier": prior},
            session=db,
        )

    await log_action(
        db,
        action=AuditAction.PAYMENT_VERIFIED,
        org_id=org.id,
        actor=actor,
        resource_type="Subscription",
        resource_id=reference,
        metadata={"paystack_status": tx_status, "upgraded": tier_upgraded},
        request=request,
    )
    await db.commit()

    return VerifyResponse(
        success=True,
        reference=reference,
        status=tx_status,
        amount_ngn=(tx.get("amount") or 0) // 100,
        org_id=org.id,
        target_tier=target_tier.value,
        tier_upgraded=tier_upgraded,
        message=(
            "Payment verified and subscription upgraded."
            if tier_upgraded
            else "Payment verified; subscription already at or above target tier."
        ),
    )


# ── Diagnostics (dev convenience) ───────────────────────────────────────────

@router.get("/config", summary="Public payment provider info (public key, no secrets)")
async def payment_config(_: User = Depends(get_current_active_user)):
    """Returns the provider name and public key so the frontend can
    render the right checkout flow without guessing."""
    settings = get_settings()
    provider = get_billing_provider()
    return {
        "provider": provider.name,
        "public_key": getattr(provider, "public_key", "") or settings.PAYSTACK_PUBLIC_KEY,
        "configured": isinstance(provider, PaystackProvider),
    }
