"""HR Manager Dashboard + My HRM Info router.

Layout:
  /hr/me                    GET/PATCH   — self-service profile
  /hr/profiles/{user_id}    GET         — admin view (within same org)
  /hr/birthdays             GET         — staff + student birthdays (month window)
  /hr/events                GET/POST    — org calendar
  /hr/events/{id}           PATCH/DELETE
  /hr/overview              GET         — headline metrics for the dashboard

Authorization:
* Self-service (`/me`)        — any authenticated user in the org.
* Admin views (`/profiles/*`, salary fields, event writes) — gated by the
  existing ``users:read`` / ``users:write`` scopes so we don't grow a
  parallel permission lattice.
* Overview + birthdays + event reads — `users:read` (HR managers and
  above already have this; keeps it consistent with /users listing).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_, extract
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.core.permissions import PermissionChecker
from app.core.workspace import effective_modules_for
from app.models.user import User, UserStatus
from app.models.organization import Organization
from app.models.hrm import HRProfile, Event
from app.models.modules.school import Student
from app.schemas.hrm import (
    HRProfileUpdate, HRProfileResponse,
    EventCreate, EventUpdate, EventResponse,
    BirthdayItem, DepartmentCount, CategoryCount, HROverview,
)

logger = logging.getLogger("extracare.hr")
router = APIRouter(prefix="/hr", tags=["HR"])

# Admin-scoped reads/writes. Reusing users:* keeps HR admin aligned with the
# existing PERMISSION_PRESETS so no role migration is needed to ship this.
_can_admin_read = Depends(PermissionChecker("users:read"))
_can_admin_write = Depends(PermissionChecker("users:write"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mask_account(n: Optional[str]) -> Optional[str]:
    """Show only the last 4 digits: '•••• 1234'. None stays None."""
    if not n:
        return n
    s = str(n)
    return f"•••• {s[-4:]}" if len(s) > 4 else "••••"


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise to a tz-aware UTC datetime.

    SQLite persists ``DateTime(timezone=True)`` columns as naive strings
    and hands them back naive, while Pydantic payloads arrive aware —
    comparing the two raises TypeError. Anchoring both to UTC here keeps
    validation portable across SQLite (dev/tests) and Postgres (prod).
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _profile_to_response(
    profile: HRProfile,
    user: User,
    *,
    include_sensitive: bool,
) -> HRProfileResponse:
    """Serialize a profile for a specific viewer.

    ``include_sensitive`` = True when the viewer is the profile owner or an
    admin (users:read). When False, salary/account/pension are masked or
    dropped — cheaper than a second schema and avoids accidental leaks
    through `exclude_unset`.
    """
    base = dict(
        id=profile.id,
        user_id=profile.user_id,
        org_id=profile.org_id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        department=user.department,
        job_title=user.job_title,
        title=profile.title,
        first_name=profile.first_name,
        middle_name=profile.middle_name,
        surname=profile.surname,
        staff_id=profile.staff_id,
        employment_status=profile.employment_status,
        gender=profile.gender,
        marital_status=profile.marital_status,
        nationality=profile.nationality,
        date_of_birth=profile.date_of_birth,
        national_id=profile.national_id,
        national_id_expiry=profile.national_id_expiry,
        address=profile.address,
        emergency_contact_name=profile.emergency_contact_name,
        emergency_contact_phone=profile.emergency_contact_phone,
        emergency_contact_relationship=profile.emergency_contact_relationship,
        hire_date=profile.hire_date,
        salary_currency=profile.salary_currency,
        bank_name=profile.bank_name,
        bank_account_name=profile.bank_account_name,
        pension_provider=profile.pension_provider,
        pension_id=profile.pension_id,
        memberships=profile.memberships or [],
        next_of_kin=profile.next_of_kin or {},
        dependents=profile.dependents or [],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
    if include_sensitive:
        base["salary"] = profile.salary
        base["bank_account_number"] = profile.bank_account_number
    else:
        base["salary"] = None
        base["bank_account_number"] = _mask_account(profile.bank_account_number)
    return HRProfileResponse(**base)


async def _get_or_create_profile(db: AsyncSession, user: User) -> HRProfile:
    """Return the user's HRProfile, creating a blank row on first access."""
    result = await db.execute(
        select(HRProfile).where(
            HRProfile.user_id == user.id,
            HRProfile.org_id == user.org_id,
            HRProfile.is_deleted == False,
        )
    )
    profile = result.scalar_one_or_none()
    if profile:
        return profile

    profile = HRProfile(
        user_id=user.id,
        org_id=user.org_id,
        memberships=[],
        next_of_kin={},
        dependents=[],
    )
    db.add(profile)
    try:
        await db.flush()
    except IntegrityError:
        # Race with another request: someone else created it — re-fetch.
        await db.rollback()
        result = await db.execute(
            select(HRProfile).where(
                HRProfile.user_id == user.id,
                HRProfile.org_id == user.org_id,
            )
        )
        profile = result.scalar_one()
    return profile


# ── Self-service profile ─────────────────────────────────────────────────────

@router.get("/me", response_model=HRProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    profile = await _get_or_create_profile(db, current_user)
    return _profile_to_response(profile, current_user, include_sensitive=True)


@router.patch("/me", response_model=HRProfileResponse)
async def update_my_profile(
    data: HRProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    profile = await _get_or_create_profile(db, current_user)
    updates = data.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(profile, key, value)

    # SQLAlchemy doesn't always detect nested JSON mutation; flag explicitly
    # when the caller sent any of the JSON-backed fields.
    from sqlalchemy.orm.attributes import flag_modified
    for json_col in ("memberships", "next_of_kin", "dependents"):
        if json_col in updates:
            flag_modified(profile, json_col)

    await db.flush()
    logger.info(
        "hr_profile.update user=%s org=%s fields=%s",
        current_user.id, current_user.org_id, list(updates.keys()),
    )
    return _profile_to_response(profile, current_user, include_sensitive=True)


@router.get("/profiles/{user_id}", response_model=HRProfileResponse, dependencies=[_can_admin_read])
async def get_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Admin view of another user's profile (same org only)."""
    user_row = (await db.execute(
        select(User).where(
            User.id == user_id,
            User.org_id == current_user.org_id,
            User.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not user_row:
        raise HTTPException(status_code=404, detail=f"User not found for id: {user_id}")

    profile = await _get_or_create_profile(db, user_row)
    return _profile_to_response(profile, user_row, include_sensitive=True)


# ── Birthdays ────────────────────────────────────────────────────────────────

@router.get("/birthdays", response_model=list[BirthdayItem], dependencies=[_can_admin_read])
async def upcoming_birthdays(
    month: Optional[int] = Query(default=None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return birthdays in the requested month (defaults to current month).

    Sourced from two tables:
      • HRProfile.date_of_birth  — staff
      • Student.date_of_birth    — students
    Results are sorted with today's birthdays first, then by day ascending.
    """
    today = date.today()
    target_month = month or today.month
    org_id = current_user.org_id
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    school_enabled = "school" in effective_modules_for(
        org.industry.value if org and org.industry else None,
        org.modules_enabled if org else [],
    )

    # ── staff ─────────────────────────────────────────────────────────────
    staff_rows = (await db.execute(
        select(HRProfile.date_of_birth, User.full_name)
        .join(User, User.id == HRProfile.user_id)
        .where(
            HRProfile.org_id == org_id,
            HRProfile.is_deleted == False,
            HRProfile.date_of_birth.is_not(None),
            extract("month", HRProfile.date_of_birth) == target_month,
            User.is_deleted == False,
        )
    )).all()

    # ── students ──────────────────────────────────────────────────────────
    student_rows = []
    if school_enabled:
        student_rows = (await db.execute(
            select(Student.date_of_birth, Student.first_name, Student.last_name)
            .where(
                Student.org_id == org_id,
                Student.is_deleted == False,
                Student.date_of_birth.is_not(None),
                extract("month", Student.date_of_birth) == target_month,
            )
        )).all()

    items: list[BirthdayItem] = []
    for dob, full_name in staff_rows:
        items.append(_birthday_item(name=full_name or "Staff", role="staff", dob=dob, today=today))
    for dob, first, last in student_rows:
        items.append(_birthday_item(name=f"{first} {last}".strip(), role="student", dob=dob, today=today))

    # Today first, then day-of-month ascending.
    items.sort(key=lambda b: (0 if b.is_today else 1, b.date_of_birth.day))
    return items


def _birthday_item(*, name: str, role: str, dob: date, today: date) -> BirthdayItem:
    is_today = (dob.month == today.month and dob.day == today.day)
    # days_until: positive = upcoming, 0 = today, negative values clamped to
    # 0 so already-happened birthdays in the selected month display as past.
    if is_today:
        days = 0
    elif dob.month == today.month:
        days = max(0, dob.day - today.day)
    else:
        days = 0
    return BirthdayItem(name=name, role=role, date_of_birth=dob, is_today=is_today, days_until=days)


# ── Events ───────────────────────────────────────────────────────────────────

@router.get("/events", response_model=list[EventResponse], dependencies=[_can_admin_read])
async def list_events(
    upcoming_only: bool = Query(default=True),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Event).where(
        Event.org_id == current_user.org_id,
        Event.is_deleted == False,
    )
    if upcoming_only:
        query = query.where(Event.starts_at >= datetime.now(timezone.utc))
    query = query.order_by(Event.starts_at.asc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()
    return [_event_to_response(e) for e in rows]


@router.post("/events", response_model=EventResponse, status_code=201, dependencies=[_can_admin_write])
async def create_event(
    data: EventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if data.ends_at and _as_utc(data.ends_at) < _as_utc(data.starts_at):
        raise HTTPException(status_code=422, detail="ends_at: must be on or after starts_at")
    event = Event(
        org_id=current_user.org_id,
        title=data.title,
        description=data.description,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        location=data.location,
        category=data.category,
        created_by=current_user.id,
    )
    db.add(event)
    await db.flush()
    logger.info("hr_event.create org=%s id=%s title=%s", current_user.org_id, event.id, event.title)
    return _event_to_response(event)


@router.patch("/events/{event_id}", response_model=EventResponse, dependencies=[_can_admin_write])
async def update_event(
    event_id: str,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = (await db.execute(
        select(Event).where(
            Event.id == event_id,
            Event.org_id == current_user.org_id,
            Event.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found for id: {event_id}")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(event, key, value)
    if event.ends_at and _as_utc(event.ends_at) < _as_utc(event.starts_at):
        raise HTTPException(status_code=422, detail="ends_at: must be on or after starts_at")
    await db.flush()
    return _event_to_response(event)


@router.delete("/events/{event_id}", status_code=204, dependencies=[_can_admin_write])
async def delete_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    event = (await db.execute(
        select(Event).where(
            Event.id == event_id,
            Event.org_id == current_user.org_id,
            Event.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail=f"Event not found for id: {event_id}")
    event.is_deleted = True
    event.deleted_at = datetime.now(timezone.utc)
    await db.flush()


def _event_to_response(e: Event) -> EventResponse:
    return EventResponse(
        id=e.id,
        title=e.title,
        description=e.description,
        starts_at=e.starts_at,
        ends_at=e.ends_at,
        location=e.location,
        category=e.category,
        created_by=e.created_by,
        created_at=e.created_at,
    )


# ── HR Overview ──────────────────────────────────────────────────────────────

_AGE_BUCKETS: list[tuple[str, int, int]] = [
    ("Under 25", 0, 24),
    ("25-34", 25, 34),
    ("35-44", 35, 44),
    ("45-54", 45, 54),
    ("55+", 55, 200),
]


@router.get("/overview", response_model=HROverview, dependencies=[_can_admin_read])
async def hr_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Headline metrics for the HR dashboard.

    All numbers are derived from live tables — no cached placeholders.
    Charts that depend on HRProfile data (gender/age) will simply be
    empty until staff fill their profiles, which is the correct
    "honest empty-state" behavior for a newly-adopted module.
    """
    org_id = current_user.org_id

    total_active_staff = int((await db.execute(
        select(func.count()).select_from(User).where(
            User.org_id == org_id,
            User.status == UserStatus.ACTIVE,
            User.is_deleted == False,
        )
    )).scalar() or 0)

    total_profiles = int((await db.execute(
        select(func.count()).select_from(HRProfile).where(
            HRProfile.org_id == org_id,
            HRProfile.is_deleted == False,
        )
    )).scalar() or 0)

    # Staff per department: unlabelled users roll up under "Unassigned" so
    # the chart doesn't lose them silently.
    dept_rows = (await db.execute(
        select(
            func.coalesce(User.department, "Unassigned").label("dept"),
            func.count().label("n"),
        )
        .where(
            User.org_id == org_id,
            User.is_deleted == False,
            User.status == UserStatus.ACTIVE,
        )
        .group_by(func.coalesce(User.department, "Unassigned"))
        .order_by(func.count().desc())
    )).all()
    staff_per_department = [DepartmentCount(department=r.dept, count=r.n) for r in dept_rows]

    # Gender distribution from HRProfile (join filters out users without profiles).
    gender_rows = (await db.execute(
        select(
            func.coalesce(HRProfile.gender, "Unspecified").label("g"),
            func.count().label("n"),
        )
        .where(
            HRProfile.org_id == org_id,
            HRProfile.is_deleted == False,
        )
        .group_by(func.coalesce(HRProfile.gender, "Unspecified"))
    )).all()
    gender_distribution = [CategoryCount(label=r.g, count=r.n) for r in gender_rows]

    # Age distribution: compute buckets in Python after pulling DOBs. The
    # row count here is staff-scale (small), so a round trip + in-memory
    # bucketing is cheaper than a vendor-specific `AGE()` expression.
    dobs = (await db.execute(
        select(HRProfile.date_of_birth).where(
            HRProfile.org_id == org_id,
            HRProfile.is_deleted == False,
            HRProfile.date_of_birth.is_not(None),
        )
    )).scalars().all()

    today = date.today()
    bucket_counts: dict[str, int] = {label: 0 for label, _, _ in _AGE_BUCKETS}
    for dob in dobs:
        age = today.year - dob.year - (1 if (today.month, today.day) < (dob.month, dob.day) else 0)
        for label, lo, hi in _AGE_BUCKETS:
            if lo <= age <= hi:
                bucket_counts[label] += 1
                break
    age_distribution = [CategoryCount(label=label, count=bucket_counts[label]) for label, _, _ in _AGE_BUCKETS]

    return HROverview(
        total_active_staff=total_active_staff,
        total_profiles=total_profiles,
        staff_per_department=staff_per_department,
        gender_distribution=gender_distribution,
        age_distribution=age_distribution,
    )
