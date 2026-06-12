"""
Correctness coverage for the dashboard aggregation endpoints. These power
widgets that stakeholders see first, so a bad sum here is the most visible
kind of bug.

We call the async route functions directly with dependencies pre-resolved
(Response, db, current_user). This skips auth scaffolding without losing
the SQL-level validation we care about.
"""

from datetime import datetime, timedelta, timezone, date as date_type
import uuid

import pytest
from fastapi import Response

from app.models.modules.school import (
    BehaviourRecord,
    BehaviourType,
    TuckshopProduct,
    TuckshopPurchase,
)
from app.routers.modules.tuckshop import sales_summary
from app.routers.modules.behaviour import school_summary


# ── Tuckshop sales/summary ────────────────────────────────────────────────────


@pytest.fixture
def today_utc():
    return datetime.now(timezone.utc).date()


async def _add_product(db, org_id, name, price) -> TuckshopProduct:
    p = TuckshopProduct(id=str(uuid.uuid4()), name=name, price=price, org_id=org_id)
    db.add(p)
    await db.commit()
    return p


async def _add_purchase(db, org_id, product, qty, when: datetime) -> TuckshopPurchase:
    p = TuckshopPurchase(
        id=str(uuid.uuid4()),
        student_id=str(uuid.uuid4()),
        product_id=product.id,
        quantity=qty,
        unit_price=product.price,
        total_price=product.price * qty,
        org_id=org_id,
        created_at=when,
    )
    db.add(p)
    await db.commit()
    return p


async def test_sales_summary_totals_today_only(db, org, teacher, today_utc):
    apple = await _add_product(db, org.id, "Apple", 100.0)
    chips = await _add_product(db, org.id, "Chips", 250.0)

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    await _add_purchase(db, org.id, apple, qty=3, when=now)          # today, 300
    await _add_purchase(db, org.id, chips, qty=2, when=now)          # today, 500
    await _add_purchase(db, org.id, apple, qty=10, when=yesterday)   # excluded

    result = await sales_summary(
        response=Response(), date=None, db=db, current_user=teacher
    )

    assert result["date"] == today_utc.isoformat()
    assert result["transactions"] == 2
    assert result["total_units"] == 5
    assert result["total_revenue"] == pytest.approx(800.0)
    # Chips outsells Apple by revenue → appears first.
    assert [p["name"] for p in result["top_products"]] == ["Chips", "Apple"]


async def test_sales_summary_past_date_has_longer_cache(db, org, teacher):
    resp = Response()
    past = (datetime.now(timezone.utc).date() - timedelta(days=3)).isoformat()
    await sales_summary(response=resp, date=past, db=db, current_user=teacher)
    assert resp.headers["cache-control"] == "private, max-age=300"


async def test_sales_summary_today_has_short_cache(db, org, teacher):
    resp = Response()
    await sales_summary(response=resp, date=None, db=db, current_user=teacher)
    assert resp.headers["cache-control"] == "private, max-age=30"


async def test_sales_summary_is_tenant_scoped(db, org, teacher):
    """A purchase in a sibling org must not leak into this org's totals."""
    from app.models.organization import Organization, IndustryType
    from app.models.user import User, UserStatus

    other_org = Organization(
        id=str(uuid.uuid4()),
        name="Other",
        slug=f"o-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL,
    )
    db.add(other_org)
    await db.commit()

    other_product = await _add_product(db, other_org.id, "OtherItem", 999.0)
    await _add_purchase(db, other_org.id, other_product, qty=5, when=datetime.now(timezone.utc))

    result = await sales_summary(
        response=Response(), date=None, db=db, current_user=teacher
    )
    assert result["transactions"] == 0
    assert result["total_revenue"] == 0.0


async def test_sales_summary_empty_day(db, org, teacher):
    result = await sales_summary(
        response=Response(), date=None, db=db, current_user=teacher
    )
    assert result["transactions"] == 0
    assert result["total_units"] == 0
    assert result["total_revenue"] == 0.0
    assert result["top_products"] == []


# ── Behaviour summary ────────────────────────────────────────────────────────


async def _add_behaviour(db, org_id, student_id, *, type_, points, category, when):
    rec = BehaviourRecord(
        id=str(uuid.uuid4()),
        student_id=student_id,
        recorded_by=str(uuid.uuid4()),
        type=type_,
        category=category,
        description="x",
        points=points,
        incident_date=when,
        org_id=org_id,
    )
    db.add(rec)
    await db.commit()
    return rec


async def test_behaviour_summary_breakdown_and_totals(db, org, teacher, student):
    today = datetime.now(timezone.utc).date()
    await _add_behaviour(db, org.id, student.id, type_=BehaviourType.POSITIVE, points=5, category="Teamwork", when=today)
    await _add_behaviour(db, org.id, student.id, type_=BehaviourType.POSITIVE, points=3, category="Teamwork", when=today)
    await _add_behaviour(db, org.id, student.id, type_=BehaviourType.NEGATIVE, points=-2, category="Punctuality", when=today)

    result = await school_summary(response=Response(), days=30, db=db, current_user=teacher)

    assert result["total_count"] == 3
    assert result["total_points"] == 6
    assert result["breakdown"]["positive"] == {"count": 2, "points": 8}
    assert result["breakdown"]["negative"] == {"count": 1, "points": -2}
    assert result["breakdown"]["neutral"] == {"count": 0, "points": 0}
    # Top categories ordered by count desc.
    assert result["top_categories"][0] == {"category": "Teamwork", "count": 2}


async def test_behaviour_summary_respects_days_window(db, org, teacher, student):
    today = datetime.now(timezone.utc).date()
    await _add_behaviour(db, org.id, student.id, type_=BehaviourType.POSITIVE, points=1, category="A", when=today)
    await _add_behaviour(
        db, org.id, student.id, type_=BehaviourType.POSITIVE, points=99,
        category="Ancient", when=today - timedelta(days=400),
    )

    result = await school_summary(response=Response(), days=30, db=db, current_user=teacher)
    assert result["total_count"] == 1
    assert result["total_points"] == 1


async def test_behaviour_summary_is_tenant_scoped(db, org, teacher, student):
    from app.models.organization import Organization, IndustryType
    today = datetime.now(timezone.utc).date()

    other_org = Organization(
        id=str(uuid.uuid4()),
        name="Other",
        slug=f"o-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL,
    )
    db.add(other_org)
    await db.commit()

    await _add_behaviour(
        db, other_org.id, str(uuid.uuid4()),
        type_=BehaviourType.POSITIVE, points=100, category="Leak", when=today,
    )

    result = await school_summary(response=Response(), days=30, db=db, current_user=teacher)
    assert result["total_count"] == 0
    assert result["total_points"] == 0


async def test_behaviour_summary_cache_header(db, org, teacher):
    resp = Response()
    await school_summary(response=resp, days=30, db=db, current_user=teacher)
    assert resp.headers["cache-control"] == "private, max-age=30"
