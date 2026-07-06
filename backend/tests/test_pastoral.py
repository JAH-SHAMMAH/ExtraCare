"""Tests for Pastoral & Boarding (Batch 4): Hostel, Exeat, Mentor Reports.

Exeat approval is safety-sensitive: only the explicit approver tier
(school_admin:write) may authorise a child leaving campus, a teacher may not,
and every decision is audited with the approver. Plus hostel allocation behaviour
and tenant isolation. Handlers called directly per convention.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student
from app.models.modules.pastoral import ExeatRequest, BoardingAllocation
from app.models.audit import AuditLog
from app.routers.modules.pastoral import (
    create_hostel, list_hostels, update_hostel,
    create_allocation, list_allocations,
    create_exeat, list_exeats, update_exeat, approve_exeat, reject_exeat, return_exeat,
    create_mentor_report, list_mentor_reports, update_mentor_report, delete_mentor_report,
)
from app.schemas.pastoral import (
    HostelCreate, HostelUpdate, AllocationCreate,
    ExeatCreate, ExeatUpdate, ExeatDecision,
    MentorReportCreate, MentorReportUpdate,
)


pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug: str) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _student2(db, org, sid="S-200") -> Student:
    s = Student(id=str(uuid.uuid4()), student_id=sid, first_name="Bem", last_name="Two", org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Hostels + Boarding ─────────────────────────────────────────────────────────

async def test_hostel_create_and_allocation_occupancy(db, org, teacher, student):
    h = await create_hostel(HostelCreate(name="Unity House", gender="boys", capacity=20),
                            request=None, db=db, current_user=teacher)
    assert h.occupancy == 0

    s2 = await _student2(db, org)
    await create_allocation(AllocationCreate(student_id=student.id, hostel_id=h.id, room="A1", bed="3"),
                            request=None, db=db, current_user=teacher)
    await create_allocation(AllocationCreate(student_id=s2.id, hostel_id=h.id),
                            request=None, db=db, current_user=teacher)

    allocs = await list_allocations(h.id, db=db, current_user=teacher)
    assert len(allocs) == 2

    listing = await list_hostels(page=1, page_size=50, db=db, current_user=teacher)
    assert listing.items[0].occupancy == 2


async def test_reallocation_deactivates_prior(db, org, teacher, student):
    h1 = await create_hostel(HostelCreate(name="House 1"), request=None, db=db, current_user=teacher)
    h2 = await create_hostel(HostelCreate(name="House 2"), request=None, db=db, current_user=teacher)
    await create_allocation(AllocationCreate(student_id=student.id, hostel_id=h1.id), request=None, db=db, current_user=teacher)
    await create_allocation(AllocationCreate(student_id=student.id, hostel_id=h2.id), request=None, db=db, current_user=teacher)
    # Student must be counted in exactly one (the latest) house.
    active = (await db.execute(
        select(BoardingAllocation).where(
            BoardingAllocation.student_id == student.id, BoardingAllocation.is_active == True)  # noqa: E712
    )).scalars().all()
    assert len(active) == 1
    assert active[0].hostel_id == h2.id


# ── Exeat: approver gating + audit ─────────────────────────────────────────────

async def test_exeat_approver_is_explicit_tier(db, org):
    # Teacher can REQUEST but cannot APPROVE; admin/manager can approve.
    teacher = await _preset_user(db, org, "teacher")
    assert teacher.has_permission("school:hostel:write") is True   # may request
    assert teacher.has_permission("school_admin:write") is False   # may NOT authorise leave
    for slug in ("org_admin", "manager"):
        approver = await _preset_user(db, org, slug)
        assert approver.has_permission("school_admin:write") is True


async def test_exeat_approve_records_approver_and_audits(db, org, teacher, student):
    admin = await _preset_user(db, org, "org_admin")
    e = await create_exeat(ExeatCreate(student_id=student.id, reason="Family event", destination="Home"),
                           request=None, db=db, current_user=teacher)
    assert e.status == "pending"
    assert e.requested_by == teacher.id

    approved = await approve_exeat(e.id, payload=ExeatDecision(decision_note="OK by housemaster"),
                                   request=None, db=db, current_user=admin)
    assert approved.status == "approved"
    assert approved.approved_by == admin.id
    assert approved.decided_at is not None

    # The authorisation is in the immutable audit log, attributed to the approver.
    logs = (await db.execute(
        select(AuditLog).where(AuditLog.org_id == org.id, AuditLog.resource_type == "ExeatRequest")
    )).scalars().all()
    decision = next(l for l in logs if l.new_values and l.new_values.get("status") == "approved")
    assert decision.actor_id == admin.id
    assert decision.new_values.get("approved_by") == admin.id


async def test_exeat_cannot_approve_twice(db, org, teacher, student):
    admin = await _preset_user(db, org, "org_admin")
    e = await create_exeat(ExeatCreate(student_id=student.id), request=None, db=db, current_user=teacher)
    await approve_exeat(e.id, payload=None, request=None, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await approve_exeat(e.id, payload=None, request=None, db=db, current_user=admin)
    assert exc.value.status_code == 409


async def test_exeat_reject_and_return_flow(db, org, teacher, student):
    admin = await _preset_user(db, org, "org_admin")
    # reject path
    e1 = await create_exeat(ExeatCreate(student_id=student.id), request=None, db=db, current_user=teacher)
    rejected = await reject_exeat(e1.id, payload=ExeatDecision(decision_note="No"), request=None, db=db, current_user=admin)
    assert rejected.status == "rejected"
    # return path requires approved first
    e2 = await create_exeat(ExeatCreate(student_id=student.id), request=None, db=db, current_user=teacher)
    with pytest.raises(HTTPException) as exc:
        await return_exeat(e2.id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409
    await approve_exeat(e2.id, payload=None, request=None, db=db, current_user=admin)
    returned = await return_exeat(e2.id, request=None, db=db, current_user=teacher)
    assert returned.status == "returned"
    assert returned.actual_return_at is not None


async def test_exeat_edit_only_when_pending(db, org, teacher, student):
    admin = await _preset_user(db, org, "org_admin")
    e = await create_exeat(ExeatCreate(student_id=student.id, destination="A"), request=None, db=db, current_user=teacher)
    await approve_exeat(e.id, payload=None, request=None, db=db, current_user=admin)
    with pytest.raises(HTTPException) as exc:
        await update_exeat(e.id, ExeatUpdate(destination="B"), db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_exeat_filter_and_tenant_scope(db, org, teacher, student):
    await create_exeat(ExeatCreate(student_id=student.id), request=None, db=db, current_user=teacher)
    pending = await list_exeats(status="pending", page=1, page_size=25, db=db, current_user=teacher)
    assert pending.total == 1
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2p@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_exeats(status=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── Mentor Reports ─────────────────────────────────────────────────────────────

async def test_mentor_report_crud(db, org, teacher, student):
    m = await create_mentor_report(
        MentorReportCreate(student_id=student.id, term="Term 1", summary="Improving", concerns="Punctuality"),
        request=None, db=db, current_user=teacher,
    )
    assert m.mentor_id == teacher.id
    assert m.student_name == "Ada Okafor"

    listing = await list_mentor_reports(student_id=student.id, mentor_id=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1

    updated = await update_mentor_report(m.id, MentorReportUpdate(summary="Much improved"), db=db, current_user=teacher)
    assert updated.summary == "Much improved"

    await delete_mentor_report(m.id, db=db, current_user=teacher)
    assert (await list_mentor_reports(student_id=None, mentor_id=None, page=1, page_size=25, db=db, current_user=teacher)).total == 0


async def test_pastoral_rbac_scopes(db, org):
    # Hostel/exeat ride school:hostel:* (covered by school:read/write hierarchy);
    # mentor reports ride school:behaviour:*. Students/parents hold neither.
    for slug in ("org_admin", "manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:hostel:read")
        assert u.has_permission("school:hostel:write")
        assert u.has_permission("school:behaviour:write")
    staff = await _preset_user(db, org, "staff")
    assert staff.has_permission("school:hostel:read")
    assert not staff.has_permission("school:hostel:write")
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:hostel:read")
        assert not u.has_permission("school:behaviour:read")
