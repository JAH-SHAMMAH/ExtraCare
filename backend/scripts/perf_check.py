"""
Performance sanity check — seeds a realistic tenant into an Alembic-migrated
DB, confirms the hot queries use the composite indexes we added in Wave 1,
and times each endpoint under light concurrency.

Runs against whatever `DATABASE_URL` is configured (default: the dev DB).
Call the aggregation / resolver functions directly so we measure backend
cost only, isolating it from auth + ASGI overhead.
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend/ to sys.path so this script runs from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import Response  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: E402

from app.database import engine, Base  # noqa: E402
from app.models.user import User, UserStatus  # noqa: E402
from app.models.organization import Organization, IndustryType  # noqa: E402
from app.models.modules.school import (  # noqa: E402
    Student, SchoolClass, BehaviourRecord, BehaviourType,
    TuckshopProduct, TuckshopPurchase, CBTExam, ExamStatus,
)
from app.core.school_identity import (  # noqa: E402
    resolve_linked_student_id, resolve_taught_class_ids,
)
from app.routers.modules.tuckshop import sales_summary  # noqa: E402
from app.routers.modules.behaviour import school_summary  # noqa: E402


Session = async_sessionmaker(engine, expire_on_commit=False)


async def seed(num_students=50, num_purchases=200, num_behaviour=100):
    """Idempotent-ish seed. Wipes and recreates our synthetic tenant."""
    async with Session() as db:
        # Fresh tenant every run so timings are comparable.
        org = Organization(
            id=str(uuid.uuid4()),
            name="Perf Tenant",
            slug=f"perf-{uuid.uuid4().hex[:8]}",
            industry=IndustryType.SCHOOL,
            modules_enabled=["school"],
        )
        db.add(org)

        teacher = User(
            id=str(uuid.uuid4()),
            email=f"teacher-{uuid.uuid4().hex[:6]}@perf.test",
            full_name="Perf Teacher",
            status=UserStatus.ACTIVE,
            org_id=org.id,
        )
        student_user = User(
            id=str(uuid.uuid4()),
            email=f"student-{uuid.uuid4().hex[:6]}@perf.test",
            full_name="Perf Student",
            status=UserStatus.ACTIVE,
            org_id=org.id,
        )
        db.add_all([teacher, student_user])

        klass = SchoolClass(
            id=str(uuid.uuid4()), name="10A",
            teacher_id=teacher.id, org_id=org.id,
        )
        db.add(klass)
        await db.flush()

        # Students: 1 matched to student_user by email, rest synthetic.
        students = [Student(
            id=str(uuid.uuid4()),
            student_id=f"S-{i:04d}",
            first_name="F", last_name="L",
            email=student_user.email if i == 0 else f"syn-{i}@perf.test",
            class_id=klass.id,
            org_id=org.id,
        ) for i in range(num_students)]
        db.add_all(students)

        # One product + N purchases spread over today + yesterday to exercise
        # the created_at range predicate.
        product = TuckshopProduct(
            id=str(uuid.uuid4()), name="Chips", price=150.0, org_id=org.id,
        )
        db.add(product)
        await db.flush()

        now = datetime.now(timezone.utc)
        purchases = [TuckshopPurchase(
            id=str(uuid.uuid4()),
            student_id=students[i % num_students].id,
            product_id=product.id,
            quantity=(i % 3) + 1,
            unit_price=product.price,
            total_price=product.price * ((i % 3) + 1),
            org_id=org.id,
            created_at=now - timedelta(hours=i % 30),  # spans today + yesterday
        ) for i in range(num_purchases)]
        db.add_all(purchases)

        today = now.date()
        behaviour = [BehaviourRecord(
            id=str(uuid.uuid4()),
            student_id=students[i % num_students].id,
            recorded_by=teacher.id,
            type=BehaviourType.POSITIVE if i % 2 == 0 else BehaviourType.NEGATIVE,
            category=["Teamwork", "Punctuality", "Effort"][i % 3],
            description="perf",
            points=(i % 5) + 1 if i % 2 == 0 else -((i % 3) + 1),
            incident_date=today - timedelta(days=i % 45),  # some inside/outside 30d window
            org_id=org.id,
        ) for i in range(num_behaviour)]
        db.add_all(behaviour)

        # One live CBT exam for later spot-checks.
        exam = CBTExam(
            id=str(uuid.uuid4()),
            title="Perf Exam",
            status=ExamStatus.PUBLISHED,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            duration_minutes=60,
            created_by=teacher.id,
            org_id=org.id,
        )
        db.add(exam)

        await db.commit()
        return {"org_id": org.id, "teacher": teacher, "student_user": student_user, "klass_id": klass.id}


async def explain(db, label: str, stmt):
    """Print the SQLite query plan for a statement so we can see index usage."""
    compiled = stmt.compile(
        compile_kwargs={"literal_binds": True}, dialect=db.bind.dialect,
    )
    rows = (await db.execute(text(f"EXPLAIN QUERY PLAN {compiled}"))).all()
    print(f"\n  [{label}]")
    for r in rows:
        print(f"    {r[-1]}")


async def audit_query_plans(ctx):
    """Read-only EXPLAIN against the hot queries — proves indexes are used."""
    async with Session() as db:
        print("--EXPLAIN QUERY PLAN ------------------------------------------")

        await explain(db, "student email → id (expects ix_students_email_org)",
            select(Student.id).where(
                Student.email == ctx["student_user"].email,
                Student.org_id == ctx["org_id"],
                Student.is_deleted == False,
            ))

        await explain(db, "teacher → class ids (expects ix_school_classes_teacher_org)",
            select(SchoolClass.id).where(
                SchoolClass.teacher_id == ctx["teacher"].id,
                SchoolClass.org_id == ctx["org_id"],
            ))

        today = datetime.now(timezone.utc).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        await explain(db, "tuckshop daily totals (expects ix_tuckshop_purchases_org_created)",
            select(TuckshopPurchase.id).where(
                TuckshopPurchase.org_id == ctx["org_id"],
                TuckshopPurchase.created_at >= start,
                TuckshopPurchase.created_at < end,
            ))

        cutoff = today - timedelta(days=30)
        await explain(db, "behaviour 30d window (expects ix_behaviour_records_org_date)",
            select(BehaviourRecord.id).where(
                BehaviourRecord.org_id == ctx["org_id"],
                BehaviourRecord.incident_date >= cutoff,
            ))


async def time_call(fn, runs=50, concurrency=10):
    """Run `fn` (an async nullary) N times, `concurrency` at a time, and
    return (min, p50, p95, max) in milliseconds."""
    sem = asyncio.Semaphore(concurrency)
    timings: list[float] = []

    async def one():
        async with sem:
            t0 = time.perf_counter()
            await fn()
            timings.append((time.perf_counter() - t0) * 1000)

    await asyncio.gather(*[one() for _ in range(runs)])
    timings.sort()
    return {
        "n": len(timings),
        "min": timings[0],
        "p50": statistics.median(timings),
        "p95": timings[int(len(timings) * 0.95)],
        "max": timings[-1],
    }


async def bench(ctx):
    print("\n--LATENCY UNDER CONCURRENCY (50 runs, 10 concurrent) ----------")

    async def sales():
        async with Session() as db:
            await sales_summary(Response(), None, db, ctx["teacher"])

    async def behaviour():
        async with Session() as db:
            await school_summary(Response(), 30, db, ctx["teacher"])

    async def student_resolve():
        async with Session() as db:
            await resolve_linked_student_id(db, ctx["student_user"])

    async def teacher_resolve():
        async with Session() as db:
            await resolve_taught_class_ids(db, ctx["teacher"])

    for label, fn in [
        ("tuckshop sales_summary (today)", sales),
        ("behaviour school_summary (30d)", behaviour),
        ("resolve_linked_student_id",     student_resolve),
        ("resolve_taught_class_ids",      teacher_resolve),
    ]:
        stats = await time_call(fn)
        print(f"  {label:40s}  "
              f"min={stats['min']:5.1f}ms  p50={stats['p50']:5.1f}ms  "
              f"p95={stats['p95']:5.1f}ms  max={stats['max']:5.1f}ms")


async def main():
    ctx = await seed()
    await audit_query_plans(ctx)
    await bench(ctx)


if __name__ == "__main__":
    asyncio.run(main())
