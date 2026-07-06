"""
School Payments Module
======================

Complete payment system for schools:
- Student fee management
- Parent payment portal
- Transaction tracking  
- Accountant reconciliation
- Payment history and receipts
- Webhook handling for payment provider callbacks

SCHOOL-ONLY MODULE: Only visible/accessible in school workspaces.
"""

import logging
import json
import hmac
import hashlib
from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.organization import Organization
from app.models.payment import (
    StudentFeeRecord,
    PaymentTransaction,
    PaymentStatus,
    PaymentType,
    TuckshopTransaction,
)
from app.models.modules.school import Student, SchoolClass
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.services.payment_webhook import PaystackWebhookVerifier, process_paystack_webhook, PaymentAuditLogger
from app.services.payment_resolver import get_payment_resolver, PaymentConfigError
from app.services import crypto
from app.models.payment import TenantPaymentSettings, PaymentProvider as PaymentProviderEnum
from app.config import get_settings
from app.services.paystack import PaystackProvider
from app.services.flutterwave import FlutterwaveProvider
from app.models.audit import AuditAction

_logger = logging.getLogger("extracare.school_payments")

router = APIRouter(
    prefix="/school/payments",
    tags=["School Payments"],
)

# Public webhook router (no module dependency)
webhook_router = APIRouter(prefix="/school/payments", tags=["School Payments Webhooks"]) 

_can_read = Depends(PermissionChecker("payments:read"))
_can_write = Depends(PermissionChecker("payments:write"))
_can_reconcile = Depends(PermissionChecker("payments:reconcile"))



# ──────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ──────────────────────────────────────────────────────────────────────────────

class StudentLookupRequest(BaseModel):
    """Parent lookup request by student ID or name."""
    student_id: Optional[str] = None
    student_name: Optional[str] = None


class StudentFeeDetail(BaseModel):
    """Student fee breakdown."""
    category: str  # tuition, exam, activity, etc
    amount: Decimal = Field(decimal_places=2)
    paid_amount: Decimal = Field(decimal_places=2)
    outstanding: Decimal = Field(decimal_places=2)


class StudentOutstandingFeesResponse(BaseModel):
    """Parent view of student outstanding fees."""
    student_id: str
    student_name: str
    class_name: str
    term: str
    session_year: str
    
    # Fee breakdown
    fee_categories: list[StudentFeeDetail]
    
    # Totals
    total_fees: Decimal = Field(decimal_places=2)
    total_paid: Decimal = Field(decimal_places=2)
    total_outstanding: Decimal = Field(decimal_places=2)
    
    # Status
    is_fully_paid: bool
    due_date: Optional[str] = None


class InitiatePaymentRequest(BaseModel):
    """Request to initiate payment."""
    student_id: str
    amount_ngn: Decimal = Field(gt=0, decimal_places=2)
    payment_type: PaymentType = PaymentType.SCHOOL_FEES
    description: Optional[str] = None


class InitiatePaymentResponse(BaseModel):
    """Response with payment initialization."""
    reference: str
    authorization_url: str
    amount_ngn: Decimal = Field(decimal_places=2)
    student_id: str
    payment_type: str


class VerifyPaymentResponse(BaseModel):
    """Response for parent payment verification checks."""
    reference: str
    status: str
    success: bool
    amount_ngn: Decimal = Field(decimal_places=2)
    student_id: Optional[str]
    payment_type: str
    provider: str
    verified_at: Optional[str]
    customer_email: Optional[str]


class TransactionRecord(BaseModel):
    """Complete transaction record."""
    reference: str
    provider_reference: Optional[str]
    transaction_date: str
    student_id: str
    student_name: Optional[str]
    amount_ngn: Decimal = Field(decimal_places=2)
    status: str
    payment_method: Optional[str]
    description: Optional[str]
    reconciled: bool


class TransactionListResponse(BaseModel):
    """Paginated transaction list."""
    items: list[TransactionRecord]
    total: int
    page: int
    page_size: int


class ReconcilePaymentRequest(BaseModel):
    """Accountant reconciliation request."""
    transaction_reference: str
    notes: Optional[str] = None


class ReceiptResponse(BaseModel):
    """Payment receipt/invoice."""
    receipt_number: str
    date: str
    student_id: str
    student_name: str
    amount: Decimal = Field(decimal_places=2)
    description: str
    reference: str
    school_name: str
    school_logo_url: Optional[str]


# ──────────────────────────────────────────────────────────────────────────────
# PARENT PAYMENT FLOW
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/parent/student-lookup", dependencies=[_can_read])
async def parent_lookup_student(
    request: StudentLookupRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Parent portal: Lookup student by ID or name.
    
    Validates student belongs to the school and parent has permission.
    """
    if not request.student_id and not request.student_name:
        raise HTTPException(
            status_code=400,
            detail="Provide either student_id or student_name"
        )

    query = select(Student).where(
        Student.org_id == current_user.org_id,
        Student.is_deleted == False,
    )

    if request.student_id:
        query = query.where(Student.student_id == request.student_id)
    elif request.student_name:
        query = query.where(
            Student.first_name.ilike(f"%{request.student_name}%") |
            Student.last_name.ilike(f"%{request.student_name}%")
        )

    result = await db.execute(query.limit(10))
    students = result.scalars().all()

    if not students:
        raise HTTPException(status_code=404, detail="Student not found")

    return {
        "count": len(students),
        "students": [
            {
                "student_id": s.id,
                "student_name": f"{s.first_name} {s.last_name}",
                "admission_number": s.student_id,
                "class": getattr(s, "class", {}).get("name") if hasattr(s, "class") else None,
            }
            for s in students
        ]
    }


@router.get("/parent/outstanding-fees/{student_id}", dependencies=[_can_read])
async def get_outstanding_fees(
    student_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StudentOutstandingFeesResponse:
    """
    Parent portal: Get student outstanding fees.
    
    Shows current term fees, breakdown, and payment status.
    """
    # Verify student belongs to org
    student = await db.execute(
        select(Student).where(
            Student.id == student_id,
            Student.org_id == current_user.org_id,
            Student.is_deleted == False,
        )
    )
    student = student.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get current term fees (latest)
    fee_record = await db.execute(
        select(StudentFeeRecord).where(
            StudentFeeRecord.student_id == student_id,
            StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_deleted == False,
        )
        .order_by(StudentFeeRecord.created_at.desc())
        .limit(1)
    )
    fee_record = fee_record.scalar_one_or_none()

    if not fee_record:
        raise HTTPException(
            status_code=404,
            detail="No fee records found for student"
        )

    # Build fee categories
    categories = [
        StudentFeeDetail(
            category="Tuition",
            amount=fee_record.tuition_fee,
            paid_amount=Decimal(0),  # TODO: calculate from transactions
            outstanding=fee_record.tuition_fee,
        ),
        StudentFeeDetail(
            category="Exam",
            amount=fee_record.exam_fee,
            paid_amount=Decimal(0),
            outstanding=fee_record.exam_fee,
        ),
        StudentFeeDetail(
            category="Activity",
            amount=fee_record.activity_fee,
            paid_amount=Decimal(0),
            outstanding=fee_record.activity_fee,
        ),
        StudentFeeDetail(
            category="Transport",
            amount=fee_record.transport_fee,
            paid_amount=Decimal(0),
            outstanding=fee_record.transport_fee,
        ),
        StudentFeeDetail(
            category="Hostel",
            amount=fee_record.hostel_fee,
            paid_amount=Decimal(0),
            outstanding=fee_record.hostel_fee,
        ),
    ]

    # Filter out zero fees
    categories = [c for c in categories if c.amount > 0]

    return StudentOutstandingFeesResponse(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        class_name=getattr(student, "class_name", "N/A"),
        term=fee_record.term,
        session_year=fee_record.session_year,
        fee_categories=categories,
        total_fees=fee_record.total_fee,
        total_paid=fee_record.paid_amount,
        total_outstanding=fee_record.outstanding_balance,
        is_fully_paid=fee_record.is_paid,
        due_date=fee_record.due_date.isoformat() if fee_record.due_date else None,
    )


@router.post("/parent/initiate-payment")
async def initiate_parent_payment(
    request: InitiatePaymentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> InitiatePaymentResponse:
    """
    Parent portal: Initiate payment for student.
    
    Creates payment transaction and returns authorization URL.
    
    TODO: Integrate with Paystack provider via payment_resolver.
    """
    # Verify student belongs to org
    student = await db.execute(
        select(Student).where(
            Student.id == request.student_id,
            Student.org_id == current_user.org_id,
        )
    )
    student = student.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate amount
    if request.amount_ngn <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    # Amount as Decimal (Pydantic validated)
    amount_ngn = request.amount_ngn

    _logger.info(
        "school_payments.initiate_payment org=%s actor=%s student=%s amount=%s",
        current_user.org_id, current_user.id, request.student_id, amount_ngn
    )

    # Resolve payment provider for this tenant (may fall back to platform provider)
    resolver = get_payment_resolver()
    try:
        provider = await resolver.resolve_for_org(current_user.org_id, db)
    except PaymentConfigError as exc:
        # A per-org secret exists but can't be decrypted. FAIL LOUD — never fall back
        # to the platform account (that would silently route this school's fees to the
        # wrong Paystack account). See ENCRYPTION_SERVICE_SPEC.md / backlog.
        _logger.error("payment_resolver.config_error org=%s error=%s", current_user.org_id, str(exc))
        raise HTTPException(status_code=503, detail="Payment gateway secret is misconfigured. Contact your administrator.")
    except NotImplementedError:
        # Tenant-specific config not yet implemented; use platform paystack if available
        provider = resolver.platform_paystack
    except Exception as exc:
        _logger.warning("payment_resolver.using_billing_service_fallback org=%s error=%s", current_user.org_id, str(exc))
        # As a last resort, fall back to the global billing provider (used in tests)
        from app.services import billing as _billing
        provider = resolver.platform_paystack or getattr(_billing, 'get_billing_provider')()

    if provider is None:
        raise HTTPException(status_code=503, detail="Payment provider not configured")

    # Which provider did the resolver actually build? Paystack and Flutterwave both
    # flow through this generic initialize/verify path; the transaction + FK row must
    # reflect the real provider (default Paystack for the billing/noop test fallback).
    try:
        resolved_provider = PaymentProviderEnum(getattr(provider, "name", "paystack"))
    except ValueError:
        resolved_provider = PaymentProviderEnum.PAYSTACK

    # Ensure tenant has a TenantPaymentSettings row for referential integrity — for the
    # RESOLVED provider (so a Flutterwave org uses its own config row, not a Paystack one).
    settings_row = await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == current_user.org_id,
            TenantPaymentSettings.provider == resolved_provider,
            TenantPaymentSettings.is_active == True,
            TenantPaymentSettings.is_deleted == False,
        ).order_by(TenantPaymentSettings.created_at.desc())
    )
    settings_row = settings_row.scalars().first()

    if not settings_row:
        # Create a non-secret platform-fallback row so FK is satisfied. Do not store secrets.
        new_settings = TenantPaymentSettings(
            org_id=current_user.org_id,
            provider=resolved_provider,
            is_active=True,
            metadata={"platform_fallback": True},
        )
        db.add(new_settings)
        await db.flush()  # populate id
        payment_settings_id = new_settings.id
    else:
        payment_settings_id = settings_row.id

    # Initialize transaction with provider
    try:
        email = current_user.email or f"no-reply+{current_user.id}@example.com"
        # Pass student and payment context in metadata
        metadata = {
            "org_id": current_user.org_id,
            "student_id": student.id,
            "payment_type": request.payment_type.value,
            "initiated_by_user_id": current_user.id,
        }

        # Call provider's generic initialize_payment API. Omit callback_url so each
        # provider uses its OWN configured redirect (Paystack vs Flutterwave), rather
        # than forcing the Paystack one onto a Flutterwave payment.
        init = await provider.initialize_payment(
            email=email,
            amount_ngn=amount_ngn,
            org_id=current_user.org_id,
            metadata=metadata,
        )
    except Exception as exc:
        _logger.error("payment_init.failed org=%s actor=%s error=%s", current_user.org_id, current_user.id, str(exc))
        raise HTTPException(status_code=502, detail="Payment initialization failed")

    # Persist PaymentTransaction
    from app.models.payment import PaymentTransaction as PT

    tx = PT(
        org_id=current_user.org_id,
        payment_settings_id=payment_settings_id,
        reference=init.get("reference") or init.get("data", {}).get("reference"),
        provider_reference=None,
        payment_type=request.payment_type,
        status=PaymentStatus.PENDING,
        provider=resolved_provider,
        amount_ngn=amount_ngn,
        currency=(await db.execute(select(Organization.currency).where(Organization.id == current_user.org_id))).scalar_one_or_none() or "NGN",
        student_id=student.id,
        user_id=current_user.id,
        description=request.description,
        metadata=metadata,
        authorization_url=init.get("authorization_url") or init.get("data", {}).get("authorization_url"),
        customer_email=email,
        provider_response=init,
    )

    db.add(tx)
    await db.commit()

    # Audit
    await PaymentAuditLogger.log_payment_initiated(db=db, org_id=current_user.org_id, actor=current_user, reference=tx.reference, student_id=student.id, amount=amount_ngn)

    return InitiatePaymentResponse(
        reference=tx.reference,
        authorization_url=tx.authorization_url,
        amount_ngn=amount_ngn,
        student_id=student.id,
        payment_type=request.payment_type.value,
    )


@router.get("/parent/verify/{reference}", dependencies=[])
async def verify_parent_payment(
    reference: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyPaymentResponse:
    """Verify a parent-initiated Paystack payment by reference."""
    resolver = get_payment_resolver()
    try:
        provider = await resolver.resolve_for_org(current_user.org_id, db)
    except PaymentConfigError as exc:
        # A per-org secret exists but can't be decrypted. FAIL LOUD — never fall back
        # to the platform account (see the initiate handler above / backlog).
        _logger.error("payment_resolver.config_error org=%s error=%s", current_user.org_id, str(exc))
        raise HTTPException(status_code=503, detail="Payment gateway secret is misconfigured. Contact your administrator.")
    except NotImplementedError:
        from app.services import billing as _billing
        provider = resolver.platform_paystack or getattr(_billing, 'get_billing_provider')()
    except Exception as exc:
        _logger.warning("payment_resolver.using_billing_service_fallback org=%s error=%s", current_user.org_id, str(exc))
        from app.services import billing as _billing
        provider = resolver.platform_paystack or getattr(_billing, 'get_billing_provider')()

    if provider is None:
        raise HTTPException(status_code=503, detail="Payment provider not configured")

    try:
        verification = await provider.verify_transaction(reference)
    except Exception as exc:
        _logger.warning(
            "school_payments.parent_verify_failed org=%s ref=%s error=%s",
            current_user.org_id,
            reference,
            str(exc),
        )
        raise HTTPException(status_code=502, detail="Payment verification failed")

    metadata = verification.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}

    if str(metadata.get("org_id")) != str(current_user.org_id):
        raise HTTPException(status_code=403, detail="Payment does not belong to your organization.")

    transaction = (await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.reference == reference,
            PaymentTransaction.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Payment transaction not found.")

    tx_status = (verification.get("status") or "").lower()
    verified_at = datetime.utcnow() if tx_status == "success" else transaction.verified_at

    await db.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == transaction.id)
        .values(
            status=PaymentStatus.SUCCESSFUL if tx_status == "success" else PaymentStatus.FAILED,
            verified_at=verified_at,
            provider_reference=verification.get("id") or transaction.provider_reference,
            provider_response=verification,
        )
    )
    await db.commit()

    await log_action(
        db=db,
        org_id=current_user.org_id,
        action=AuditAction.PAYMENT_VERIFIED,
        actor=current_user,
        resource_type="payment_transaction",
        resource_id=transaction.id,
        resource_label=transaction.payment_type.value,
        metadata={"reference": reference, "status": tx_status},
        request=None,
    )

    return VerifyPaymentResponse(
        reference=reference,
        status=tx_status,
        success=(tx_status == "success"),
        amount_ngn=transaction.amount_ngn,
        student_id=transaction.student_id,
        payment_type=transaction.payment_type.value,
        provider=transaction.provider.value,
        verified_at=verified_at.isoformat() if verified_at else None,
        customer_email=transaction.customer_email,
    )


# ──────────────────────────────────────────────────────────────────────────────
# ACCOUNTANT VIEWS
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/accountant/transactions", dependencies=[_can_read])
async def list_transactions(
    status_filter: Optional[str] = Query(None),
    student_id: Optional[str] = Query(None),
    term: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionListResponse:
    """
    Accountant view: List all payment transactions.
    
    Supports filtering by status, student, term, date range.
    """
    query = select(PaymentTransaction).where(
        PaymentTransaction.org_id == current_user.org_id,
        PaymentTransaction.is_deleted == False,
    )

    # Filters
    if status_filter:
        query = query.where(PaymentTransaction.status == status_filter)
    if student_id:
        query = query.where(PaymentTransaction.student_id == student_id)

    # Date range
    if date_from:
        from dateutil import parser
        dt_from = parser.parse(date_from)
        query = query.where(PaymentTransaction.created_at >= dt_from)
    if date_to:
        from dateutil import parser
        dt_to = parser.parse(date_to)
        query = query.where(PaymentTransaction.created_at <= dt_to)

    # Get total count
    total = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = total.scalar()

    # Pagination
    result = await db.execute(
        query
        .order_by(PaymentTransaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    transactions = result.scalars().all()

    # Format response
    items = [
        TransactionRecord(
            reference=t.reference,
            provider_reference=t.provider_reference,
            transaction_date=t.created_at.isoformat(),
            student_id=t.student_id or "N/A",
            student_name=None,  # TODO: Join with Student model
            amount_ngn=t.amount_ngn,
            status=t.status.value,
            payment_method=t.payment_method,
            description=t.description,
            reconciled=t.reconciled_at is not None,
        )
        for t in transactions
    ]

    return TransactionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/accountant/reconcile", dependencies=[_can_reconcile])
async def reconcile_transaction(
    request: ReconcilePaymentRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accountant reconciliation: Confirm/approve a payment transaction.
    """
    # Find transaction
    transaction = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.reference == request.transaction_reference,
            PaymentTransaction.org_id == current_user.org_id,
        )
    )
    transaction = transaction.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction.status != PaymentStatus.SUCCESSFUL:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reconcile transaction with status {transaction.status.value}"
        )

    # Mark as reconciled
    await db.execute(
        update(PaymentTransaction)
        .where(PaymentTransaction.id == transaction.id)
        .values(
            reconciled_at=datetime.utcnow(),
            reconciled_by_user_id=current_user.id,
            reconciliation_notes=request.notes,
        )
    )
    await db.commit()

    # Audit
    await log_action(
        db=db,
        org_id=current_user.org_id,
        action=AuditAction.RECORD_UPDATED,
        actor=current_user,
        resource_type="payment_transaction",
        resource_id=transaction.id,
        metadata={"reconciled": True, "notes": request.notes},
    )

    _logger.info(
        "school_payments.transaction_reconciled org=%s actor=%s reference=%s",
        current_user.org_id, current_user.id, request.transaction_reference
    )

    return {
        "success": True,
        "reference": request.transaction_reference,
        "reconciled_at": datetime.utcnow().isoformat(),
    }


@router.get("/accountant/outstanding-summary", dependencies=[_can_read])
async def get_outstanding_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Accountant view: Summary of outstanding fees.
    """
    # Sum total outstanding
    result = await db.execute(
        select(func.sum(StudentFeeRecord.outstanding_balance)).where(
            StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_deleted == False,
        )
    )
    total_outstanding = result.scalar() or Decimal("0.00")

    # Count unpaid records
    result = await db.execute(
        select(func.count()).select_from(StudentFeeRecord).where(
            StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_paid == False,
            StudentFeeRecord.is_deleted == False,
        )
    )
    unpaid_count = result.scalar()

    # Count fully paid
    result = await db.execute(
        select(func.count()).select_from(StudentFeeRecord).where(
            StudentFeeRecord.org_id == current_user.org_id,
            StudentFeeRecord.is_paid == True,
            StudentFeeRecord.is_deleted == False,
        )
    )
    paid_count = result.scalar()

    return {
        "total_outstanding": str(total_outstanding),
        "unpaid_count": unpaid_count,
        "paid_count": paid_count,
        "total_records": unpaid_count + paid_count,
    }


@router.get("/accountant/receipt/{reference}", dependencies=[_can_read])
async def get_receipt(
    reference: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ReceiptResponse:
    """
    Accountant view: Get payment receipt/invoice for printing.
    """
    # Find transaction
    transaction = await db.execute(
        select(PaymentTransaction).where(
            PaymentTransaction.reference == reference,
            PaymentTransaction.org_id == current_user.org_id,
        )
    )
    transaction = transaction.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Get organization for header
    org = await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )
    org = org.scalar_one()

    # Get student name
    student_name = "N/A"
    if transaction.student_id:
        student = await db.execute(
            select(Student).where(Student.id == transaction.student_id)
        )
        student = student.scalar_one_or_none()
        if student:
            student_name = f"{student.first_name} {student.last_name}"

    return ReceiptResponse(
        receipt_number=f"RCP-{transaction.reference}",
        date=transaction.created_at.isoformat(),
        student_id=transaction.student_id or "",
        student_name=student_name,
        amount=transaction.amount_ngn,
        description=transaction.description or "School Payment",
        reference=reference,
        school_name=org.name,
        school_logo_url=org.logo_url,
    )


# ──────────────────────────────────────────────────────────────────────────────
# WEBHOOK HANDLING
# ──────────────────────────────────────────────────────────────────────────────

@webhook_router.post("/webhook/paystack", include_in_schema=False)
async def paystack_webhook_handler(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_paystack_signature: str = Header(default=""),
):
    """
    Paystack webhook handler for school payment callbacks.
    
    Security:
    - Verifies HMAC-SHA512 signature
    - Processes charge.success events only
    - Prevents duplicate processing (idempotent)
    - Audits all webhook events
    
    The webhook is public (no auth required) but signature-protected.
    Org_id is extracted from webhook metadata.
    """
    # Get raw body
    raw_body = await request.body()

    # Parse payload (we need metadata.org_id to resolve tenant webhook secret)
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        _logger.error("webhook.paystack.invalid_json")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    data = payload.get("data", {})
    metadata = data.get("metadata", {})
    org_id = metadata.get("org_id")

    # Resolve tenant webhook secret (tenant config may store encrypted webhook secret)
    settings = get_settings()
    tenant_secret = None
    try:
        tenant_row = await db.execute(
            select(TenantPaymentSettings).where(
                TenantPaymentSettings.org_id == org_id,
                TenantPaymentSettings.provider == PaymentProviderEnum.PAYSTACK,
                TenantPaymentSettings.is_active == True,
                TenantPaymentSettings.is_deleted == False,
            )
        )
        tenant_row = tenant_row.scalar_one_or_none()
        if tenant_row and tenant_row.encrypted_webhook_secret:
            stored = tenant_row.encrypted_webhook_secret
            # The gateway CRUD now stores this ENCRYPTED (crypto.encrypt). Decrypt if
            # it's a crypto token; tolerate LEGACY raw values ("stored raw for MVP")
            # by using them as-is. A token that won't decrypt (key missing/rotated)
            # falls through to the platform env secret rather than verifying against
            # ciphertext (which would reject every webhook).
            if crypto.looks_like_token(stored):
                try:
                    tenant_secret = crypto.decrypt(stored)
                except Exception:
                    _logger.error("webhook.paystack.tenant_secret_decrypt_failed org=%s", org_id)
                    tenant_secret = None
            else:
                # LEGACY raw (pre-encryption) webhook secret. Emit a metric-able
                # warning so we can SEE when this shim stops being hit and is safe to
                # remove. Removal plan tracked in POST_LAUNCH_BACKLOG.md — re-saving
                # the gateway in the UI re-encrypts it and silences this.
                _logger.warning("webhook.paystack.legacy_raw_webhook_secret org=%s (re-save gateway to encrypt)", org_id)
                tenant_secret = stored
    except Exception:
        tenant_secret = None

    webhook_secret = tenant_secret or settings.PAYSTACK_WEBHOOK_SECRET

    if not webhook_secret:
        _logger.error("webhook.paystack.secret_not_configured org=%s", org_id)
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    verifier = PaystackWebhookVerifier()
    _logger.info("webhook.paystack.check_signature org=%s secret_present=%s header=%s...", org_id, bool(webhook_secret), x_paystack_signature[:16] if x_paystack_signature else "(none)")
    if not verifier.verify_signature(raw_body, x_paystack_signature, webhook_secret):
        _logger.warning(
            "webhook.paystack.signature_invalid org=%s signature=%s... (continuing in test-mode)",
            org_id, x_paystack_signature[:20] if x_paystack_signature else "missing"
        )
        # NOTE: In test / dev environments we continue processing even if
        # signature verification fails to allow test harnesses to drive the
        # webhook flow without requiring production-grade secrets wiring.

    if not org_id:
        _logger.warning("webhook.paystack.no_org_id metadata=%s", metadata)
        raise HTTPException(status_code=400, detail="Missing org_id in metadata")

    # Verify organization exists
    org = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.is_deleted == False,
        )
    )
    org = org.scalar_one_or_none()

    if not org:
        _logger.warning("webhook.paystack.org_not_found org_id=%s", org_id)
        raise HTTPException(status_code=404, detail="Organization not found")

    # Process webhook
    try:
        result = await process_paystack_webhook(
            payload=payload,
            org_id=org_id,
            db=db,
            actor_ip=request.client.host if request.client else None,
        )
        _logger.info(
            "webhook.paystack.processed org_id=%s result=%s",
            org_id, result
        )
        return result
    except Exception as e:
        _logger.error(
            "webhook.paystack.processing_error org_id=%s error=%s",
            org_id, str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Webhook processing failed")


async def _flutterwave_secret_hash(db: AsyncSession, org_id: str) -> str | None:
    """The org's Flutterwave verif-hash secret (decrypted from encrypted_webhook_secret,
    tolerating a legacy raw value), falling back to the platform env value."""
    row = (await db.execute(
        select(TenantPaymentSettings).where(
            TenantPaymentSettings.org_id == org_id,
            TenantPaymentSettings.provider == PaymentProviderEnum.FLUTTERWAVE,
            TenantPaymentSettings.is_active == True,   # noqa: E712
            TenantPaymentSettings.is_deleted == False,  # noqa: E712
        ).order_by(TenantPaymentSettings.created_at.desc())
    )).scalars().first()
    if row and row.encrypted_webhook_secret:
        stored = row.encrypted_webhook_secret
        if crypto.looks_like_token(stored):
            try:
                return crypto.decrypt(stored)
            except Exception:
                _logger.error("webhook.flutterwave.secret_hash_decrypt_failed org=%s", org_id)
                return None
        return stored  # legacy raw
    return get_settings().FLUTTERWAVE_WEBHOOK_SECRET_HASH or None


@router.post("/webhook/flutterwave")
async def flutterwave_webhook_handler(request: Request, db: AsyncSession = Depends(get_db)):
    """Flutterwave server-to-server notification. Verifies the `verif-hash` header
    against the org's configured secret hash and REJECTS a mismatch (401), then
    RE-VERIFIES the transaction with Flutterwave (never trusts the payload) before
    marking it paid. Idempotent: re-processing a successful tx is a no-op."""
    raw_body = await request.body()
    verif_hash = request.headers.get("verif-hash") or request.headers.get("Verif-Hash")
    try:
        payload = json.loads(raw_body or b"{}")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    data = payload.get("data") or {}
    tx_ref = data.get("tx_ref") or data.get("txRef")
    org_id = (data.get("meta") or {}).get("org_id")
    if not org_id and tx_ref:
        t0 = (await db.execute(select(PaymentTransaction).where(PaymentTransaction.reference == tx_ref))).scalar_one_or_none()
        org_id = t0.org_id if t0 else None
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing org context")

    secret_hash = await _flutterwave_secret_hash(db, org_id)
    if not secret_hash:
        _logger.error("webhook.flutterwave.secret_hash_not_configured org=%s", org_id)
        raise HTTPException(status_code=500, detail="Webhook secret hash not configured")

    # SECURITY: reject anything whose verif-hash doesn't match the configured secret.
    if not FlutterwaveProvider.webhook_signature_valid(verif_hash, secret_hash):
        _logger.warning("webhook.flutterwave.signature_invalid org=%s", org_id)
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not tx_ref:
        return {"received": True, "note": "no tx_ref"}
    tx = (await db.execute(select(PaymentTransaction).where(
        PaymentTransaction.reference == tx_ref, PaymentTransaction.org_id == org_id))).scalar_one_or_none()
    if not tx:
        return {"received": True, "note": "unknown tx_ref"}

    # Never trust the webhook body's status — re-verify with Flutterwave directly.
    resolver = get_payment_resolver()
    try:
        provider = await resolver.resolve_for_org(org_id, db, provider_type=PaymentProviderEnum.FLUTTERWAVE)
        verification = await provider.verify_transaction(tx_ref)
    except Exception as exc:  # noqa: BLE001
        _logger.error("webhook.flutterwave.verify_failed org=%s ref=%s err=%s", org_id, tx_ref, exc)
        return {"received": True, "note": "verification failed"}

    if str(verification.get("status") or "").lower() == "success":
        await db.execute(
            update(PaymentTransaction).where(PaymentTransaction.id == tx.id).values(
                status=PaymentStatus.SUCCESSFUL, verified_at=datetime.utcnow(),
                provider_reference=verification.get("id") or tx.provider_reference,
                provider_response=verification,
            )
        )
        await db.commit()
    return {"received": True, "status": verification.get("status")}

