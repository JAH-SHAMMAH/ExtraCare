"""
Tuckshop coverage — financial integrity + tenant isolation.

Success path (stock decrement + total) plus the forbidden/validation paths:
insufficient stock, inactive product, non-positive quantity, and a cross-tenant
student id (must 404, never bill a foreign student).
"""

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.organization import Organization, IndustryType
from app.models.modules.school import Student, TuckshopProduct
from app.routers.modules.tuckshop import create_product, record_purchase
from app.schemas.school_experience import TuckshopProductCreate, TuckshopPurchaseCreate

pytestmark = pytest.mark.asyncio


async def _product(db, teacher, **kw):
    payload = {"name": "Juice", "price": 2.5, "stock": 10}
    payload.update(kw)
    return await create_product(payload=TuckshopProductCreate(**payload), db=db, current_user=teacher)


async def test_purchase_decrements_stock_and_totals(db, org, teacher, student):
    prod = await _product(db, teacher, stock=10, price=2.5)
    res = await record_purchase(
        payload=TuckshopPurchaseCreate(student_id=student.id, product_id=prod["id"], quantity=3),
        db=db, current_user=teacher,
    )
    assert res["total_price"] == 7.5
    p = (await db.execute(select(TuckshopProduct).where(TuckshopProduct.id == prod["id"]))).scalar_one()
    assert p.stock == 7


async def test_purchase_insufficient_stock_400(db, org, teacher, student):
    prod = await _product(db, teacher, stock=1)
    with pytest.raises(HTTPException) as ei:
        await record_purchase(
            payload=TuckshopPurchaseCreate(student_id=student.id, product_id=prod["id"], quantity=5),
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 400


async def test_purchase_inactive_product_400(db, org, teacher, student):
    prod = await _product(db, teacher, is_active=False)
    with pytest.raises(HTTPException) as ei:
        await record_purchase(
            payload=TuckshopPurchaseCreate(student_id=student.id, product_id=prod["id"], quantity=1),
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 400


async def test_purchase_nonpositive_quantity_400(db, org, teacher, student):
    prod = await _product(db, teacher)
    with pytest.raises(HTTPException) as ei:
        await record_purchase(
            payload=TuckshopPurchaseCreate(student_id=student.id, product_id=prod["id"], quantity=0),
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 400


async def test_purchase_cross_tenant_student_404(db, org, teacher):
    other = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other)
    await db.flush()
    foreign_student = Student(
        id=str(uuid.uuid4()), student_id="X-1", first_name="Z", last_name="Z", org_id=other.id,
    )
    db.add(foreign_student)
    await db.flush()
    prod = await _product(db, teacher)
    with pytest.raises(HTTPException) as ei:
        await record_purchase(
            payload=TuckshopPurchaseCreate(student_id=foreign_student.id, product_id=prod["id"], quantity=1),
            db=db, current_user=teacher,
        )
    assert ei.value.status_code == 404
