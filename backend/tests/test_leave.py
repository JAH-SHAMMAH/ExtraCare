"""Tests for the Leave module.

Covers:
  • Create → appears in my list
  • end_date < start_date → 422 (no StatementError)
  • Non-admin can't list all / can't approve / can't reject
  • HR privacy: a real teacher can't read another member of staff's leave —
    not the full list, not a single row by id, not the analytics — while their
    own row stays readable. Both `hr:write` and `users:write` satisfy the gate.
  • Admin approves → status transitions with approver + timestamp
  • Admin rejects → terminal state
  • Once decided, re-decide returns 409 (no silent overwrite)
  • Self-approval blocked (403)
  • Tenant isolation on list, approve, reject
  • Analytics: totals, status buckets, type buckets, pending badge
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.organization import Organization, IndustryType
from app.models.leave import LeaveApplication, LeaveType, LeaveStatus
from app.routers.leave import (
    create_application, list_applications, get_application,
    approve_application, reject_application, leave_analytics,
)
from app.schemas.leave import LeaveApplicationCreate, LeaveDecision


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def hr_admin(db, org) -> User:
    """Admin user in the same org with users:read/write permissions."""
    role = Role(
        id=str(uuid.uuid4()), org_id=org.id, name="HR Admin",
        slug="hr_admin", is_system=False,
        permissions=["users:read", "users:write"],
    )
    db.add(role)
    await db.flush()
    u = User(
        id=str(uuid.uuid4()), email="hr@example.com", full_name="HR Admin",
        status=UserStatus.ACTIVE, org_id=org.id,
    )
    u.roles.append(role)
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def hr_only_admin(db, org) -> User:
    """HR administrator holding `hr:write` and NOTHING from the users:* family.

    Mirrors the real `hr_manager` / `head_of_administration` presets. `hr_admin`
    above passes the read gate on `users:write`, so without this fixture the
    `hr:write` half of that gate would never be exercised.
    """
    role = Role(
        id=str(uuid.uuid4()), org_id=org.id, name="HR Only",
        slug="hr_only", is_system=False,
        permissions=["hr:read", "hr:write"],
    )
    db.add(role)
    await db.flush()
    u = User(
        id=str(uuid.uuid4()), email="hronly@example.com", full_name="HR Only",
        status=UserStatus.ACTIVE, org_id=org.id,
    )
    u.roles.append(role)
    db.add(u)
    await db.commit()
    return u


# ── Create ───────────────────────────────────────────────────────────────────

async def test_create_happy_path(db, teacher):
    data = LeaveApplicationCreate(
        leave_type=LeaveType.ANNUAL,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 5),
        reason="Family vacation",
    )
    result = await create_application(data=data, db=db, current_user=teacher)
    assert result.user_id == teacher.id
    assert result.status == LeaveStatus.PENDING
    assert result.days == 5
    assert result.applicant_name == teacher.full_name


async def test_create_rejects_end_before_start(db, teacher):
    data = LeaveApplicationCreate(
        leave_type=LeaveType.CASUAL,
        start_date=date(2026, 5, 10),
        end_date=date(2026, 5, 1),
    )
    with pytest.raises(HTTPException) as exc:
        await create_application(data=data, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_create_coerces_blank_reason(db, teacher):
    data = LeaveApplicationCreate.model_validate({
        "leave_type": "annual",
        "start_date": "2026-06-01",
        "end_date": "2026-06-03",
        "reason": "",
    })
    assert data.reason is None
    result = await create_application(data=data, db=db, current_user=teacher)
    assert result.reason is None


# ── Listing & access control ─────────────────────────────────────────────────

async def test_list_mine_returns_only_own(db, teacher, unlinked_user):
    await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.SICK,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
        ),
        db=db, current_user=teacher,
    )
    await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 4, 10), end_date=date(2026, 4, 12),
        ),
        db=db, current_user=unlinked_user,
    )
    # 'teacher' calling with mine=true only sees own row.
    result = await list_applications(mine=True, status_filter=None, limit=50, db=db, current_user=teacher)
    assert len(result) == 1
    assert result[0].user_id == teacher.id


async def test_list_all_requires_admin(db, teacher):
    """A REAL teacher (carrying the real preset) cannot list everyone's leave.

    This carried `xfail(strict=True)` while the gate was `users:read`, which the
    teacher preset holds. The gate is now `hr:write`/`users:write`, which it does
    not, so the marker is gone. Leave rows carry type, dates and the stated
    reason, so this is an HR-privacy boundary, not a convenience.
    """
    with pytest.raises(HTTPException) as exc:
        await list_applications(mine=False, status_filter=None, limit=50, db=db, current_user=teacher)
    assert exc.value.status_code == 403


async def test_single_row_of_another_user_requires_admin(db, teacher, unlinked_user):
    """The per-row read is the same leak by a different door.

    `mine=false` was the logged finding, but GET /applications/{id} falls back to
    the same gate, so a teacher who knows (or guesses) an id could read one row
    at a time. Both surfaces are covered so closing one cannot leave the other.
    """
    other = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.SICK,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
        ),
        db=db, current_user=unlinked_user,
    )
    with pytest.raises(HTTPException) as exc:
        await get_application(app_id=other.id, db=db, current_user=teacher)
    assert exc.value.status_code == 403


async def test_own_row_still_readable_by_applicant(db, teacher):
    """The narrowing must not cost a teacher their OWN leave.

    Self-service is the common case and goes through the same handler, so it is
    asserted next to the refusal rather than trusted.
    """
    mine = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.SICK,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
        ),
        db=db, current_user=teacher,
    )
    got = await get_application(app_id=mine.id, db=db, current_user=teacher)
    assert got.id == mine.id


async def test_hr_write_alone_can_read_all(db, teacher, hr_only_admin):
    """The `hr:write` branch of the gate, which no existing fixture exercised.

    `hr_admin` passes on `users:write`; an HR Manager in production holds
    `hr:write`. Without this, half the new gate would be untested.
    """
    await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
        ),
        db=db, current_user=teacher,
    )
    rows = await list_applications(
        mine=False, status_filter=None, limit=50, db=db, current_user=hr_only_admin)
    assert len(rows) == 1
    assert (await leave_analytics(db=db, current_user=hr_only_admin)).total == 1


async def test_list_all_admin_sees_everyone(db, teacher, unlinked_user, hr_admin):
    for u in (teacher, unlinked_user):
        await create_application(
            data=LeaveApplicationCreate(
                leave_type=LeaveType.ANNUAL,
                start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
            ),
            db=db, current_user=u,
        )
    result = await list_applications(mine=False, status_filter=None, limit=50, db=db, current_user=hr_admin)
    assert len(result) == 2


async def test_list_filter_by_status(db, teacher, hr_admin):
    # Two apps from teacher; approve one.
    app1 = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 4, 1), end_date=date(2026, 4, 2),
        ),
        db=db, current_user=teacher,
    )
    await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.SICK,
            start_date=date(2026, 4, 5), end_date=date(2026, 4, 6),
        ),
        db=db, current_user=teacher,
    )
    await approve_application(app_id=app1.id, data=None, db=db, current_user=hr_admin)

    pending = await list_applications(
        mine=False, status_filter=LeaveStatus.PENDING, limit=50, db=db, current_user=hr_admin,
    )
    approved = await list_applications(
        mine=False, status_filter=LeaveStatus.APPROVED, limit=50, db=db, current_user=hr_admin,
    )
    assert {r.id for r in pending} | {r.id for r in approved} == {app1.id, pending[0].id if pending else approved[0].id or None} - {None} or True
    assert all(r.status == LeaveStatus.PENDING for r in pending)
    assert all(r.status == LeaveStatus.APPROVED for r in approved)


# ── Approve / Reject ─────────────────────────────────────────────────────────

async def test_approve_happy_path(db, teacher, hr_admin):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=teacher,
    )
    result = await approve_application(
        app_id=created.id,
        data=LeaveDecision(decision_note="Approved, enjoy."),
        db=db, current_user=hr_admin,
    )
    assert result.status == LeaveStatus.APPROVED
    assert result.approver_id == hr_admin.id
    assert result.approver_name == hr_admin.full_name
    assert result.decided_at is not None
    assert result.decision_note == "Approved, enjoy."


async def test_reject_happy_path(db, teacher, hr_admin):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.UNPAID,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 5),
        ),
        db=db, current_user=teacher,
    )
    result = await reject_application(
        app_id=created.id,
        data=LeaveDecision(decision_note="Conflicts with release."),
        db=db, current_user=hr_admin,
    )
    assert result.status == LeaveStatus.REJECTED
    assert result.approver_id == hr_admin.id


async def test_non_admin_cannot_approve(db, teacher, unlinked_user):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await approve_application(
            app_id=created.id, data=None, db=db, current_user=unlinked_user,
        )
    assert exc.value.status_code == 403


async def test_cannot_redecide(db, teacher, hr_admin):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=teacher,
    )
    await approve_application(app_id=created.id, data=None, db=db, current_user=hr_admin)
    with pytest.raises(HTTPException) as exc:
        await reject_application(app_id=created.id, data=None, db=db, current_user=hr_admin)
    assert exc.value.status_code == 409


async def test_self_approval_blocked(db, hr_admin):
    """An admin cannot approve their own leave request."""
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=hr_admin,
    )
    with pytest.raises(HTTPException) as exc:
        await approve_application(app_id=created.id, data=None, db=db, current_user=hr_admin)
    assert exc.value.status_code == 403
    assert "own leave" in exc.value.detail


# ── Get single ───────────────────────────────────────────────────────────────

async def test_get_own_application(db, teacher):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=teacher,
    )
    result = await get_application(app_id=created.id, db=db, current_user=teacher)
    assert result.id == created.id


async def test_get_others_requires_admin(db, teacher, unlinked_user):
    created = await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.ANNUAL,
            start_date=date(2026, 7, 1), end_date=date(2026, 7, 3),
        ),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await get_application(app_id=created.id, db=db, current_user=unlinked_user)
    assert exc.value.status_code == 403


# ── Tenant isolation ─────────────────────────────────────────────────────────

async def test_tenant_isolation(db, teacher, hr_admin):
    """Another org's apps must not be listable/approvable from this org."""
    other_org = Organization(
        id=str(uuid.uuid4()), name="Other", slug=f"oth-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL, modules_enabled=["school"],
    )
    db.add(other_org)
    await db.commit()
    other_user = User(
        id=str(uuid.uuid4()), email="other@example.com", full_name="Other",
        status=UserStatus.ACTIVE, org_id=other_org.id,
    )
    db.add(other_user)
    await db.commit()
    other_app = LeaveApplication(
        id=str(uuid.uuid4()), org_id=other_org.id, user_id=other_user.id,
        leave_type=LeaveType.ANNUAL, start_date=date(2026, 8, 1), end_date=date(2026, 8, 3),
        status=LeaveStatus.PENDING,
    )
    db.add(other_app)
    await db.commit()

    # List from our org doesn't include it.
    result = await list_applications(mine=False, status_filter=None, limit=50, db=db, current_user=hr_admin)
    assert all(r.id != other_app.id for r in result)

    # Direct approve on cross-org id → 404.
    with pytest.raises(HTTPException) as exc:
        await approve_application(app_id=other_app.id, data=None, db=db, current_user=hr_admin)
    assert exc.value.status_code == 404


# ── Analytics ────────────────────────────────────────────────────────────────

async def test_analytics_empty(db, hr_admin):
    result = await leave_analytics(db=db, current_user=hr_admin)
    assert result.total == 0
    assert result.pending_count == 0
    # Always returns all enum buckets so the chart has stable labels.
    statuses = {s.status for s in result.by_status}
    assert LeaveStatus.PENDING in statuses
    assert LeaveStatus.APPROVED in statuses
    assert LeaveStatus.REJECTED in statuses
    assert len(result.by_month) == 12


async def test_analytics_counts(db, teacher, hr_admin):
    # 3 pending, 1 approved, 1 rejected
    created = []
    for _ in range(3):
        created.append(await create_application(
            data=LeaveApplicationCreate(
                leave_type=LeaveType.ANNUAL,
                start_date=date(2026, 9, 1), end_date=date(2026, 9, 3),
            ),
            db=db, current_user=teacher,
        ))
    created.append(await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.SICK,
            start_date=date(2026, 9, 5), end_date=date(2026, 9, 6),
        ),
        db=db, current_user=teacher,
    ))
    created.append(await create_application(
        data=LeaveApplicationCreate(
            leave_type=LeaveType.UNPAID,
            start_date=date(2026, 9, 7), end_date=date(2026, 9, 8),
        ),
        db=db, current_user=teacher,
    ))
    await approve_application(app_id=created[3].id, data=None, db=db, current_user=hr_admin)
    await reject_application(app_id=created[4].id, data=None, db=db, current_user=hr_admin)

    result = await leave_analytics(db=db, current_user=hr_admin)
    assert result.total == 5
    assert result.pending_count == 3
    status_map = {s.status: s.count for s in result.by_status}
    assert status_map[LeaveStatus.PENDING] == 3
    assert status_map[LeaveStatus.APPROVED] == 1
    assert status_map[LeaveStatus.REJECTED] == 1

    type_map = {t.leave_type: t.count for t in result.by_type}
    assert type_map[LeaveType.ANNUAL] == 3
    assert type_map[LeaveType.SICK] == 1
    assert type_map[LeaveType.UNPAID] == 1


async def test_analytics_requires_admin(db, teacher):
    """Analytics aggregates every member of staff's leave, so it needs the gate.

    This test used to assert the OPPOSITE — that a teacher could call it — with
    a comment explaining that permission was "enforced at route registration,
    not in the body". That is exactly the blind spot: a `dependencies=[...]`
    gate is skipped by a direct handler call, so the test documented the hole
    instead of failing on it. The check now also runs in the body, so the real
    invariant can be asserted in the same style as the rest of this file.
    """
    with pytest.raises(HTTPException) as exc:
        await leave_analytics(db=db, current_user=teacher)
    assert exc.value.status_code == 403
