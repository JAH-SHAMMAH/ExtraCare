"""
Shared fixtures for the Wave 3 test suite.

Uses an in-memory SQLite DB per test to keep the suite fast and isolated.
We bypass the FastAPI auth layer by constructing User/Organization rows
directly and passing them to route handlers / helpers as plain arguments.
Route handlers in this codebase accept `current_user` + `db` as regular
parameters after FastAPI extracts them from `Depends`, so calling them as
coroutines with those args in place works without rebuilding the stack.
"""

from __future__ import annotations

import os

# The historical suite exercises the retained multi-tenant engine
# (registration, onboarding, plan caps, industry isolation). The production
# default is single-school mode; force multi-tenant for these legacy tests.
# Must be set BEFORE any app module imports get_settings() (lru-cached on first
# call below). New single-school tests opt back in at runtime.
os.environ.setdefault("SINGLE_SCHOOL_MODE", "false")

# Disable rate limiting by default for the whole suite. Many tests loop over an
# endpoint (registering ~15 orgs from the same client IP, seeding users, etc.)
# and would otherwise trip shared-IP/org buckets. test_rate_limit.py re-enables
# it locally to assert the limiter behaves. Set BEFORE any app import.
os.environ.setdefault("RATE_LIMITS_ENABLED", "false")

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base
# Import every module once so Base.metadata is populated before create_all.
from app.models import user as _user, organization as _org, role as _role, audit as _audit, import_job as _ij  # noqa: F401
from app.models.modules import school as _school, hospital as _hospital, business as _business  # noqa: F401
from app.models.modules import admissions as _admissions  # noqa: F401
from app.models.modules import academics as _academics  # noqa: F401
from app.models.modules import pastoral as _pastoral  # noqa: F401
from app.models.modules import finance as _finance  # noqa: F401
from app.models.modules import wallet as _wallet  # noqa: F401
from app.models.modules import operations as _operations  # noqa: F401
from app.models.modules import platform as _platform  # noqa: F401
from app.models import hrm as _hrm  # noqa: F401  (StaffAssessment / TalentCandidate)
from app.models import support as _support  # noqa: F401
from app.models import payment as _payment  # noqa: F401  (StudentFeeRecord — FeeDiscount FKs to it)
from app.models.modules import remita as _remita  # noqa: F401
from app.models import hr_extended as _hr_extended  # noqa: F401

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.modules.school import Student, SchoolClass


@pytest_asyncio.fixture
async def engine():
    # Each test gets its own in-memory DB: fast, fully isolated, no cleanup.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def org(db) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name="Test School",
        slug=f"test-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL,
        modules_enabled=["school"],
    )
    db.add(o)
    await db.commit()
    return o


@pytest_asyncio.fixture
async def teacher(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="teacher@example.com",
        full_name="Teacher One",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    # Loaded (empty) roles so has_permission() doesn't lazy-load in async direct
    # calls — mirrors production, where get_current_user selectinloads roles.
    u.roles = []
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def student_user(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="student@example.com",
        full_name="Student One",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def unlinked_user(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="stranger@example.com",
        full_name="Unlinked Staff",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def school_class(db, org, teacher) -> SchoolClass:
    c = SchoolClass(
        id=str(uuid.uuid4()),
        name="Year 10A",
        level="Secondary",
        academic_year="2025/2026",
        teacher_id=teacher.id,
        org_id=org.id,
    )
    db.add(c)
    await db.commit()
    return c


@pytest_asyncio.fixture
async def student(db, org, school_class, student_user) -> Student:
    s = Student(
        id=str(uuid.uuid4()),
        student_id="S-001",
        first_name="Ada",
        last_name="Okafor",
        email=student_user.email,  # link via shared email
        class_id=school_class.id,
        org_id=org.id,
    )
    db.add(s)
    await db.commit()
    return s


def utc(y, m, d, hh=0, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)
