"""Facility Management: lookups, facility links, the Complaint → Inspection →
Maintenance → Requisition workflow chain, tiered approval, report, audit view, RBAC.
Handlers called directly per the conftest convention.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.schemas.facility import (
    NameCreate, FacilityCreate, ComplaintCreate, InspectionCreate,
    MaintenanceCreate, MaintenanceUpdate, ApprovalLevelCreate, RequisitionCreate, DisburseInput, StaffCreate,
)
from app.routers.modules.facility import (
    create_type, list_types, create_location,
    create_facility, list_facilities, update_facility,
    create_complaint, list_complaints, create_inspection,
    create_maintenance, update_maintenance,
    create_approval_level, create_requisition, approve_requisition, disburse_requisition,
    create_staff, list_staff, facility_report, facility_audit,
)

pytestmark = pytest.mark.asyncio


async def _staff(db, org, slug="manager") -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


# ── Lookups + facility links ──────────────────────────────────────────────────

async def test_facility_with_type_location_manager(db, org):
    staff = await _staff(db, org)
    t = await create_type(NameCreate(name="Electrical"), db=db, current_user=staff)
    loc = await create_location(NameCreate(name="Reception"), db=db, current_user=staff)
    f = await create_facility(
        FacilityCreate(name="Smartboard", facility_type_id=t.id, quantity=14,
                       location_ids=[loc.id], manager_ids=[staff.id]),
        request=None, db=db, current_user=staff)
    assert f.facility_type_name == "Electrical" and f.quantity == 14
    assert f.location_names == ["Reception"] and f.manager_names == [staff.full_name]

    listed = await list_facilities(db=db, current_user=staff)
    assert len(listed) == 1 and listed[0].inspection_count == 0


async def test_types_are_tenant_scoped(db, org):
    staff = await _staff(db, org)
    await create_type(NameCreate(name="OrgA type"), db=db, current_user=staff)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    other_staff = await _staff(db, other)
    assert await list_types(db=db, current_user=other_staff) == []


# ── Workflow chain ─────────────────────────────────────────────────────────────

async def test_complaint_inspection_moves_status(db, org):
    staff = await _staff(db, org)
    c = await create_complaint(ComplaintCreate(title="Broken AC"), request=None, db=db, current_user=staff)
    assert c.reference.startswith("FC-") and c.status == "open" and c.lodger_name == staff.full_name

    await create_inspection(InspectionCreate(complaint_id=c.id, comment="Checked, compressor failed"),
                            request=None, db=db, current_user=staff)
    updated = (await list_complaints(mine=False, db=db, current_user=staff))[0]
    assert updated.status == "in_progress" and updated.inspection_count == 1


async def test_maintenance_lifecycle(db, org):
    staff = await _staff(db, org)
    c = await create_complaint(ComplaintCreate(title="Leak"), request=None, db=db, current_user=staff)
    m = await create_maintenance(MaintenanceCreate(complaint_id=c.id, maintenance_type="repair", total_cost=Decimal("5000")),
                                 request=None, db=db, current_user=staff)
    assert m.status == "pending" and m.total_cost == Decimal("5000")
    done = await update_maintenance(m.id, MaintenanceUpdate(status="completed"), request=None, db=db, current_user=staff)
    assert done.status == "completed"
    with pytest.raises(HTTPException) as ei:
        await update_maintenance(m.id, MaintenanceUpdate(status="banana"), request=None, db=db, current_user=staff)
    assert ei.value.status_code == 422


async def test_requisition_tiered_approval_and_disburse(db, org):
    staff = await _staff(db, org)
    await create_approval_level(ApprovalLevelCreate(name="Basic", threshold=Decimal("0")), db=db, current_user=staff)
    ext = await create_approval_level(ApprovalLevelCreate(name="Extended", threshold=Decimal("15000")), db=db, current_user=staff)
    # cost 20,000 → routes to the Extended level (highest threshold ≤ cost)
    r = await create_requisition(RequisitionCreate(title="Fix roof", requisition_cost=Decimal("20000")),
                                 request=None, db=db, current_user=staff)
    assert r.status == "pending" and r.approval_level_name == "Extended" and r.approval_level_id == ext.id

    approved = await approve_requisition(r.id, request=None, db=db, current_user=staff)
    assert approved.status == "approved" and approved.total_approved == Decimal("20000") and approved.approval_date is not None

    disbursed = await disburse_requisition(r.id, DisburseInput(), request=None, db=db, current_user=staff)
    assert disbursed.status == "disbursed" and disbursed.total_disbursed == Decimal("20000")

    # can't disburse a non-approved requisition
    r2 = await create_requisition(RequisitionCreate(title="x", requisition_cost=Decimal("100")), request=None, db=db, current_user=staff)
    with pytest.raises(HTTPException) as ei:
        await disburse_requisition(r2.id, DisburseInput(), request=None, db=db, current_user=staff)
    assert ei.value.status_code == 409


# ── Staff pools + report + audit ────────────────────────────────────────────────

async def test_staff_pool_and_role_validation(db, org):
    staff = await _staff(db, org)
    s = await create_staff(StaffCreate(user_id=staff.id, role_type="store_keeper"), db=db, current_user=staff)
    assert s.role_type == "store_keeper" and s.user_name == staff.full_name
    assert len(await list_staff(role_type="store_keeper", db=db, current_user=staff)) == 1
    with pytest.raises(HTTPException) as ei:
        await create_staff(StaffCreate(user_id=staff.id, role_type="wizard"), db=db, current_user=staff)
    assert ei.value.status_code == 422


async def test_report_and_audit_view(db, org):
    staff = await _staff(db, org)
    await create_complaint(ComplaintCreate(title="A"), request=None, db=db, current_user=staff)
    rep = await facility_report(db=db, current_user=staff)
    assert rep["cards"]["complaints"] == 1 and rep["pending_complaints"] == 1
    # audit view reads the GLOBAL log filtered to facility resource types
    aud = await facility_audit(category="complaints", db=db, current_user=staff)
    assert any("complaint" in (i["activity"] or "").lower() for i in aud["items"])


# ── RBAC ────────────────────────────────────────────────────────────────────────

async def test_facilities_role_scope(db, org):
    fac = await _staff(db, org, "facilities")
    assert fac.has_permission("school_admin:facility:read") and fac.has_permission("school_admin:facility:write")
    # a teacher (broad school:read/write) does NOT reach the school_admin namespace
    teacher = await _staff(db, org, "teacher")
    assert not teacher.has_permission("school_admin:facility:read")
    # org_admin + manager inherit it via the broad school_admin grant
    mgr = await _staff(db, org, "manager")
    assert mgr.has_permission("school_admin:facility:read") and mgr.has_permission("school_admin:facility:write")
