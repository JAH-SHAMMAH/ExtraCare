"""
Tuckshop Router
================
Products and purchases for the school tuckshop.

Stock is decremented on purchase. The user's request mentioned an optional
wallet — not implemented here to keep scope tight; purchases simply record
who sold what to whom and for how much. A wallet balance ledger can be added
later as a sibling table without changing this schema.

RBAC:
  - school:read   → browse products, view purchase history (students their own)
  - school:write  → add / edit products, record sales
"""

from datetime import date as date_type, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import TuckshopProduct, TuckshopPurchase, Student
from app.schemas.school_experience import (
    TuckshopProductCreate,
    TuckshopProductUpdate,
    TuckshopProductResponse,
    TuckshopPurchaseCreate,
    TuckshopPurchaseResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/tuckshop",
    tags=["Tuckshop"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))


# ── Products ──────────────────────────────────────────────────────────────────


@router.get("/products", dependencies=[_can_read])
async def list_products(
    category: str | None = None,
    is_active: bool | None = None,
    low_stock: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(TuckshopProduct).where(
        TuckshopProduct.org_id == current_user.org_id,
        TuckshopProduct.is_deleted == False,
    )
    if category:
        query = query.where(TuckshopProduct.category == category)
    if is_active is not None:
        query = query.where(TuckshopProduct.is_active == is_active)
    if low_stock:
        query = query.where(TuckshopProduct.stock < 10)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(TuckshopProduct.name.asc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [TuckshopProductResponse.model_validate(p).model_dump() for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/products", status_code=201, dependencies=[_can_write])
async def create_product(
    payload: TuckshopProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = TuckshopProduct(**payload.model_dump(), org_id=current_user.org_id)
    db.add(product)
    await db.flush()
    return TuckshopProductResponse.model_validate(product).model_dump()


@router.patch("/products/{product_id}", dependencies=[_can_write])
async def update_product(
    product_id: str,
    payload: TuckshopProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = await _get_product_or_404(db, product_id, current_user.org_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    await db.flush()
    return TuckshopProductResponse.model_validate(product).model_dump()


@router.delete("/products/{product_id}", status_code=204, dependencies=[_can_write])
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    product = await _get_product_or_404(db, product_id, current_user.org_id)
    product.is_deleted = True
    product.is_active = False


# ── Purchases ─────────────────────────────────────────────────────────────────


@router.post("/purchases", status_code=201, dependencies=[_can_write])
async def record_purchase(
    payload: TuckshopPurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive.")

    product = await _get_product_or_404(db, payload.product_id, current_user.org_id)
    if not product.is_active:
        raise HTTPException(status_code=400, detail="Product is inactive.")
    if product.stock < payload.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock.")

    # Verify student in tenant — prevents a school staffer from billing
    # a student record that belongs to a different organization.
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    total = round(product.price * payload.quantity, 2)
    purchase = TuckshopPurchase(
        student_id=payload.student_id,
        product_id=product.id,
        quantity=payload.quantity,
        unit_price=product.price,
        total_price=total,
        sold_by=current_user.id,
        org_id=current_user.org_id,
    )
    product.stock -= payload.quantity
    db.add(purchase)
    await db.flush()
    return TuckshopPurchaseResponse.model_validate(purchase).model_dump()


@router.get("/purchases", dependencies=[_can_read])
async def list_purchases(
    student_id: str | None = None,
    product_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(TuckshopPurchase).where(TuckshopPurchase.org_id == current_user.org_id)
    if student_id:
        query = query.where(TuckshopPurchase.student_id == student_id)
    if product_id:
        query = query.where(TuckshopPurchase.product_id == product_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(TuckshopPurchase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [TuckshopPurchaseResponse.model_validate(p).model_dump() for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ── Aggregations ─────────────────────────────────────────────────────────────


@router.get("/sales/summary", dependencies=[_can_read])
async def sales_summary(
    response: Response,
    date: str | None = Query(default=None, description="ISO date (YYYY-MM-DD). Defaults to today (UTC)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lightweight read-optimised aggregate for the tuckshop dashboard widget."""
    # Today's totals change with every sale — keep the window tight. Past days
    # are effectively immutable, so past-day requests get a longer cache.
    target = date_type.fromisoformat(date) if date else datetime.now(timezone.utc).date()
    is_past = target < datetime.now(timezone.utc).date()
    response.headers["Cache-Control"] = "private, max-age=300" if is_past else "private, max-age=30"
    start = datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    base = select(TuckshopPurchase).where(
        TuckshopPurchase.org_id == current_user.org_id,
        TuckshopPurchase.created_at >= start,
        TuckshopPurchase.created_at < end,
    ).subquery()

    totals = (await db.execute(
        select(
            func.coalesce(func.sum(base.c.total_price), 0.0),
            func.coalesce(func.sum(base.c.quantity), 0),
            func.count(base.c.id),
        )
    )).one()

    top_rows = (await db.execute(
        select(
            TuckshopPurchase.product_id,
            TuckshopProduct.name,
            func.sum(TuckshopPurchase.quantity).label("units"),
            func.sum(TuckshopPurchase.total_price).label("revenue"),
        )
        .join(TuckshopProduct, TuckshopProduct.id == TuckshopPurchase.product_id)
        .where(
            TuckshopPurchase.org_id == current_user.org_id,
            TuckshopPurchase.created_at >= start,
            TuckshopPurchase.created_at < end,
        )
        .group_by(TuckshopPurchase.product_id, TuckshopProduct.name)
        .order_by(func.sum(TuckshopPurchase.total_price).desc())
        .limit(5)
    )).all()

    return {
        "date": target.isoformat(),
        "total_revenue": float(totals[0] or 0),
        "total_units": int(totals[1] or 0),
        "transactions": int(totals[2] or 0),
        "top_products": [
            {"product_id": r.product_id, "name": r.name, "units": int(r.units or 0), "revenue": float(r.revenue or 0)}
            for r in top_rows
        ],
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_product_or_404(db: AsyncSession, product_id: str, org_id: str) -> TuckshopProduct:
    result = await db.execute(
        select(TuckshopProduct).where(
            TuckshopProduct.id == product_id,
            TuckshopProduct.org_id == org_id,
            TuckshopProduct.is_deleted == False,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")
    return product
