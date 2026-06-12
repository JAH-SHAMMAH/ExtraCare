"""
Payment Webhook Handler & Verification
=======================================

Secure webhook processing for payment provider callbacks.

Security:
- HMAC signature verification before any state mutation
- Idempotency checks to prevent duplicate processing
- Audit trail of all webhook events
- Never trust webhook data alone - verify with provider
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction
from app.models.payment import (
    PaymentProvider,
    PaymentStatus,
    PaymentTransaction,
    PaymentWebhookEvent,
)
from app.models.user import User
from app.services.audit_service import log_action
from app.services.payment_resolver import get_payment_resolver

_logger = logging.getLogger("extracare.payment_webhook")


class PaystackWebhookVerifier:
    """
    Verify Paystack webhook signatures using HMAC-SHA512.
    
    Security critical: Signature must be verified before processing.
    """

    @staticmethod
    def verify_signature(payload: bytes | str, signature: str, secret: str) -> bool:
        """
        Verify Paystack webhook signature.
        
        Args:
            payload: Raw request body as bytes or string
            signature: X-Paystack-Signature header value
            secret: Paystack webhook secret key
            
        Returns:
            True if signature is valid
        """
        # Accept either bytes or str payloads; compute HMAC over bytes.
        if isinstance(payload, str):
            payload_bytes = payload.encode()
        else:
            payload_bytes = payload
        hash = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()
        _logger.info("webhook.verify computed=%s provided=%s", hash[:16], signature[:16] if signature else "(none)")
        return hash == signature

    from app.models.payment import PaymentWebhookEvent, PaymentProvider as PaymentProviderEnum, TenantPaymentSettings

async def process_paystack_webhook(
    payload: dict,
    org_id: str,
    db: AsyncSession,
    actor_ip: Optional[str] = None,
    raw_body: bytes | None = None,
) -> dict:
    """Process Paystack webhook events with idempotency and provider verification."""
    event = payload.get("event", "")
    data = payload.get("data", {}) or {}
    reference = data.get("reference")
    raw_hash = hashlib.sha256(raw_body).hexdigest() if raw_body else None

    existing_event = None
    if raw_hash:
        existing = await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.raw_hash == raw_hash,
            )
        )
        existing_event = existing.scalar_one_or_none()
        if existing_event:
            if existing_event.processed:
                _logger.info("webhook.paystack.duplicate_raw_hash org=%s ref=%s", org_id, reference)
                return {"processed": True, "reason": "Duplicate webhook payload"}
        else:
            existing_event = PaymentWebhookEvent(
                org_id=org_id,
                provider=PaymentProvider.PAYSTACK,
                event_type=event,
                event_reference=reference,
                raw_hash=raw_hash,
                received_at=datetime.now(timezone.utc),
                processed=False,
                raw_payload=payload,
            )
            db.add(existing_event)
            await db.flush()

    _logger.info("webhook.paystack.received org=%s event=%s reference=%s", org_id, event, reference)

    if event != "charge.success":
        _logger.debug("webhook.paystack.ignored event=%s (not charge.success)", event)
        return {"processed": False, "reason": f"Event {event} not processed"}

    if not reference:
        _logger.warning("webhook.paystack.no_reference org=%s", org_id)
        return {"processed": False, "reason": "No reference in payload"}

    result = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.reference == reference,
            PaymentTransaction.org_id == org_id,
        )
    )
    transaction = result.scalar_one_or_none()

    resolver = get_payment_resolver()
    try:
        provider = await resolver.resolve_for_org(org_id, db)
    except Exception:
        provider = resolver.platform_paystack

    try:
        verification = await provider.verify_transaction(reference)
    except Exception as exc:
        _logger.error("webhook.paystack.verify_call_failed org=%s ref=%s error=%s", org_id, reference, str(exc))
        if existing_event:
            await db.execute(
                update(PaymentWebhookEvent)
                .where(PaymentWebhookEvent.id == existing_event.id)
                .values(processed=False)
            )
            await db.commit()
        return {"processed": False, "reason": "Provider verification failed"}

    prov_metadata = verification.get("metadata") or {}
    if isinstance(prov_metadata, str):
        try:
            prov_metadata = json.loads(prov_metadata)
        except Exception:
            prov_metadata = {}

    prov_status = verification.get("status")
    prov_amount = verification.get("amount")
    try:
        prov_amount_ngn = float(prov_amount) / 100 if prov_amount is not None else None
    except Exception:
        prov_amount_ngn = None

    if str(prov_metadata.get("org_id")) != str(org_id):
        _logger.error(
            "webhook.paystack.org_mismatch org_claim=%s provider=%s",
            org_id, prov_metadata.get("org_id")
        )
        await PaymentAuditLogger.log_payment_failed(
            db=db,
            org_id=org_id,
            reference=reference,
            error_message="org_id mismatch in provider verification",
        )
        return {"processed": False, "reason": "Org mismatch"}

    if transaction and prov_amount_ngn is not None and float(transaction.amount_ngn) != float(prov_amount_ngn):
        _logger.error(
            "webhook.paystack.amount_mismatch org=%s ref=%s tx_amount=%s provider_amount=%s",
            org_id, reference, transaction.amount_ngn, prov_amount_ngn,
        )
        await PaymentAuditLogger.log_payment_failed(
            db=db,
            org_id=org_id,
            reference=reference,
            error_message="amount mismatch",
        )
        return {"processed": False, "reason": "Amount mismatch"}

    if not transaction:
        _logger.warning("webhook.paystack.transaction_not_found org=%s reference=%s", org_id, reference)
        return {"processed": False, "reason": "Transaction not found"}

    if transaction.status == PaymentStatus.SUCCESSFUL and transaction.verified_at:
        _logger.info(
            "webhook.paystack.duplicate org=%s reference=%s (already verified)",
            org_id, reference,
        )
        if existing_event:
            await db.execute(
                update(PaymentWebhookEvent)
                .where(PaymentWebhookEvent.id == existing_event.id)
                .values(processed=True, processed_at=datetime.now(timezone.utc))
            )
            await db.commit()
        return {"processed": True, "reason": "Already verified (idempotency)"}

    amount_charged = data.get("amount", 0) / 100
    payment_status = data.get("status", "")
    authorization = data.get("authorization") or {}
    customer_email = data.get("customer", {}).get("email")

    await db.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == transaction.id)
        .where(or_(PaymentTransaction.status != PaymentStatus.SUCCESSFUL, PaymentTransaction.verified_at == None))
        .values(
            status=PaymentStatus.SUCCESSFUL if prov_status == "success" else PaymentStatus.FAILED,
            verified_at=datetime.now(timezone.utc),
            verification_code=prov_status,
            provider_reference=verification.get("id") or data.get("id"),
            provider_response=verification,
            last_4_digits=authorization.get("last4"),
            payment_method=authorization.get("card_type"),
            customer_email=customer_email,
        )
    )

    if existing_event:
        await db.execute(
            update(PaymentWebhookEvent)
            .where(PaymentWebhookEvent.id == existing_event.id)
            .values(processed=True, processed_at=datetime.now(timezone.utc))
        )

    await db.commit()

    await log_action(
        db=db,
        org_id=org_id,
        action=AuditAction.PAYMENT_VERIFIED,
        actor=None,
        resource_type="payment_transaction",
        resource_id=transaction.id,
        metadata={
            "event": event,
            "verified": prov_status == "success",
            "amount": amount_charged,
            "reference": reference,
        },
    )

    _logger.info("webhook.paystack.processed org=%s reference=%s status=%s", org_id, reference, payment_status)
    return {"processed": True, "reference": reference, "status": payment_status, "amount": amount_charged}


class PaymentAuditLogger:
    """
    Audit logging for payment operations.
    """

    @staticmethod
    async def log_payment_initiated(
        db: AsyncSession,
        org_id: str,
        actor: User | None,
        reference: str,
        student_id: Optional[str],
        amount: float,
    ) -> None:
        """Log payment initialization."""
        await log_action(
            db=db,
            org_id=org_id,
            action=AuditAction.PAYMENT_INITIATED,
            actor=actor,
            resource_type="payment_transaction",
            resource_id=reference,
            metadata={
                "event": "payment_initiated",
                "student_id": student_id,
                "amount": amount,
                "reference": reference,
            },
        )

    @staticmethod
    async def log_payment_verified(
        db: AsyncSession,
        org_id: str,
        reference: str,
        verification_result: str,
    ) -> None:
        """Log payment verification result."""
        await log_action(
            db=db,
            org_id=org_id,
            action=AuditAction.PAYMENT_VERIFIED,
            actor=None,
            resource_type="payment_transaction",
            resource_id=reference,
            metadata={
                "event": "payment_verified",
                "result": verification_result,
            },
        )

    @staticmethod
    async def log_payment_reconciled(
        db: AsyncSession,
        org_id: str,
        actor: User | None,
        reference: str,
        notes: Optional[str] = None,
    ) -> None:
        """Log payment reconciliation by accountant."""
        await log_action(
            db=db,
            org_id=org_id,
            action=AuditAction.RECORD_UPDATED,
            actor=actor,
            resource_type="payment_transaction",
            resource_id=reference,
            metadata={
                "event": "payment_reconciled",
                "reconciled_by": actor.id if actor else None,
                "notes": notes,
            },
        )

    @staticmethod
    async def log_payment_failed(
        db: AsyncSession,
        org_id: str,
        reference: str,
        error_message: str,
    ) -> None:
        """Log payment failure."""
        await log_action(
            db=db,
            org_id=org_id,
            action=AuditAction.PAYMENT_FAILED,
            actor=None,
            resource_type="payment_transaction",
            resource_id=reference,
            metadata={
                "event": "payment_failed",
                "error": error_message,
            },
        )
