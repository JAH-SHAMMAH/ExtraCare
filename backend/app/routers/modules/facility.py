"""Facility Management router (Educare parity), prefix ``/facility``.

Managed lookups (types/locations/departments), role-assignment pools, and the
Complaint → Inspection → Maintenance → Requisition workflow chain + tiered
approval levels. Audit Trail is a filtered VIEW over the global AuditLog (no
facility audit table). A requisition disbursement records state on the
requisition; posting the spend to the general ledger reuses the finance ledger
service (tracked via journal_entry_id) — see notes on `disburse`.

RBAC: everything gates on ``school_admin:facility:read`` / ``:write``. org_admin +
manager inherit it via their broad ``school_admin:read/write`` (scope hierarchy);
a dedicated ``facilities`` role holds only the facility child scope.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.audit import AuditLog, AuditAction
from app.models.modules.operations import (
    Facility, FacilityType, FacilityLocation, FacilityLocationTag, FacilityDepartment,
    FacilityStaff, FacilityManagerLink, FacilityComplaint, FacilityInspection,
    FacilityMaintenance, FacilityApprovalLevel, FacilityRequisition,
)
from app.schemas.facility import (
    NameCreate, NameUpdate, LookupResponse, DepartmentResponse,
    FacilityCreate, FacilityUpdate, FacilityResponse,
    StaffCreate, StaffResponse, _STAFF_ROLES,
    ComplaintCreate, ComplaintUpdate, ComplaintResponse, _COMPLAINT_STATUSES,
    InspectionCreate, InspectionUpdate, InspectionResponse,
    MaintenanceCreate, MaintenanceUpdate, MaintenanceResponse, _MAINT_STATUSES,
    ApprovalLevelCreate, ApprovalLevelUpdate, ApprovalLevelResponse,
    RequisitionCreate, RequisitionUpdate, RequisitionResponse, DisburseInput,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action

router = APIRouter(prefix="/facility", tags=["Facility Management"],
                   dependencies=[Depends(require_role_module("school"))])

_read = Depends(PermissionChecker("school_admin:facility:read"))
_write = Depends(PermissionChecker("school_admin:facility:write"))

FACILITY_RESOURCE_TYPES = ["Facility", "FacilityComplaint", "FacilityInspection",
                           "FacilityMaintenance", "FacilityRequisition"]


# ── shared helpers ───────────────────────────────────────────────────────────

async def _load(db, model, obj_id, org_id, label):
    obj = (await db.execute(select(model).where(model.id == obj_id, model.org_id == org_id))).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail=f"{label} not found.")
    return obj


async def _user_names(db, org_id, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(User.id, User.full_name).where(User.org_id == org_id, User.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def _facility_names(db, org_id, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(Facility.id, Facility.name).where(Facility.org_id == org_id, Facility.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


def _ref(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


async def _audit(db, org_id, user, action, rtype, rid, label, request=None, severity="info"):
    await log_action(db, action, org_id, actor=user, resource_type=rtype,
                     resource_id=rid, resource_label=label, severity=severity, request=request)


# ── Generic lookup CRUD (types / locations) ──────────────────────────────────

def _lookup_routes(path: str, model, label: str):
    @router.get(f"/{path}", response_model=list[LookupResponse], dependencies=[_read], name=f"list_{path}")
    async def _list(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
        rows = (await db.execute(select(model).where(model.org_id == current_user.org_id).order_by(model.name))).scalars().all()
        return [LookupResponse.model_validate(r) for r in rows]

    @router.post(f"/{path}", response_model=LookupResponse, status_code=201, dependencies=[_write], name=f"create_{path}")
    async def _create(payload: NameCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
        obj = model(name=payload.name, org_id=current_user.org_id)
        db.add(obj)
        await db.flush()
        return LookupResponse.model_validate(obj)

    @router.patch(f"/{path}/{{obj_id}}", response_model=LookupResponse, dependencies=[_write], name=f"update_{path}")
    async def _update(obj_id: str, payload: NameUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
        obj = await _load(db, model, obj_id, current_user.org_id, label)
        if payload.name is not None:
            obj.name = payload.name
        await db.flush()
        return LookupResponse.model_validate(obj)

    @router.delete(f"/{path}/{{obj_id}}", status_code=204, dependencies=[_write], name=f"delete_{path}")
    async def _delete(obj_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
        obj = await _load(db, model, obj_id, current_user.org_id, label)
        await db.delete(obj)

    return _list, _create, _update, _delete


list_types, create_type, update_type, delete_type = _lookup_routes("types", FacilityType, "Type")
list_locations, create_location, update_location, delete_location = _lookup_routes("locations", FacilityLocation, "Location")


# ── Departments (with officer count) ─────────────────────────────────────────

@router.get("/departments", response_model=list[DepartmentResponse], dependencies=[_read])
async def list_departments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(FacilityDepartment).where(FacilityDepartment.org_id == current_user.org_id).order_by(FacilityDepartment.name))).scalars().all()
    counts = dict((await db.execute(
        select(FacilityStaff.department_id, func.count(FacilityStaff.id))
        .where(FacilityStaff.org_id == current_user.org_id, FacilityStaff.role_type == "officer")
        .group_by(FacilityStaff.department_id))).all())
    return [DepartmentResponse(id=d.id, name=d.name, org_id=d.org_id, officer_count=counts.get(d.id, 0)) for d in rows]


@router.post("/departments", response_model=DepartmentResponse, status_code=201, dependencies=[_write])
async def create_department(payload: NameCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = FacilityDepartment(name=payload.name, org_id=current_user.org_id)
    db.add(d)
    await db.flush()
    return DepartmentResponse(id=d.id, name=d.name, org_id=d.org_id, officer_count=0)


@router.patch("/departments/{dept_id}", response_model=DepartmentResponse, dependencies=[_write])
async def update_department(dept_id: str, payload: NameUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = await _load(db, FacilityDepartment, dept_id, current_user.org_id, "Department")
    if payload.name is not None:
        d.name = payload.name
    await db.flush()
    return DepartmentResponse(id=d.id, name=d.name, org_id=d.org_id, officer_count=0)


@router.delete("/departments/{dept_id}", status_code=204, dependencies=[_write])
async def delete_department(dept_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    d = await _load(db, FacilityDepartment, dept_id, current_user.org_id, "Department")
    await db.delete(d)


# ── Facility staff / role pools ──────────────────────────────────────────────

@router.get("/staff", response_model=list[StaffResponse], dependencies=[_read])
async def list_staff(role_type: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(FacilityStaff).where(FacilityStaff.org_id == current_user.org_id)
    if role_type:
        q = q.where(FacilityStaff.role_type == role_type)
    rows = (await db.execute(q)).scalars().all()
    names = await _user_names(db, current_user.org_id, {r.user_id for r in rows})
    return [StaffResponse(id=r.id, user_id=r.user_id, user_name=names.get(r.user_id), role_type=r.role_type, department_id=r.department_id, org_id=r.org_id) for r in rows]


@router.post("/staff", response_model=StaffResponse, status_code=201, dependencies=[_write])
async def create_staff(payload: StaffCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.role_type not in _STAFF_ROLES:
        raise HTTPException(status_code=422, detail=f"role_type must be one of {sorted(_STAFF_ROLES)}")
    await _load(db, User, payload.user_id, current_user.org_id, "User")
    if payload.department_id:
        await _load(db, FacilityDepartment, payload.department_id, current_user.org_id, "Department")
    s = FacilityStaff(user_id=payload.user_id, role_type=payload.role_type, department_id=payload.department_id, org_id=current_user.org_id)
    db.add(s)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {s.user_id})
    return StaffResponse(id=s.id, user_id=s.user_id, user_name=names.get(s.user_id), role_type=s.role_type, department_id=s.department_id, org_id=s.org_id)


@router.delete("/staff/{staff_id}", status_code=204, dependencies=[_write])
async def delete_staff(staff_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    s = await _load(db, FacilityStaff, staff_id, current_user.org_id, "Staff assignment")
    await db.delete(s)


# ── Facilities ───────────────────────────────────────────────────────────────

async def _facility_dict(db, f: Facility, org_id) -> FacilityResponse:
    type_name = None
    if f.facility_type_id:
        t = (await db.execute(select(FacilityType.name).where(FacilityType.id == f.facility_type_id))).scalar_one_or_none()
        type_name = t
    loc_rows = (await db.execute(
        select(FacilityLocation.id, FacilityLocation.name)
        .join(FacilityLocationTag, FacilityLocationTag.location_id == FacilityLocation.id)
        .where(FacilityLocationTag.facility_id == f.id))).all()
    mgr_rows = (await db.execute(
        select(User.id, User.full_name).join(FacilityManagerLink, FacilityManagerLink.user_id == User.id)
        .where(FacilityManagerLink.facility_id == f.id))).all()
    insp = (await db.execute(select(func.count(FacilityInspection.id)).where(FacilityInspection.facility_id == f.id))).scalar() or 0
    return FacilityResponse(
        id=f.id, name=f.name, facility_type_id=f.facility_type_id, facility_type_name=type_name,
        quantity=f.quantity, notes=f.notes, is_active=f.is_active,
        location_ids=[r[0] for r in loc_rows], location_names=[r[1] for r in loc_rows],
        manager_ids=[r[0] for r in mgr_rows], manager_names=[r[1] for r in mgr_rows],
        inspection_count=insp, org_id=f.org_id, created_at=f.created_at)


async def _set_facility_links(db, f, org_id, location_ids, manager_ids):
    if location_ids is not None:
        await db.execute(delete(FacilityLocationTag).where(FacilityLocationTag.facility_id == f.id))
        for lid in location_ids:
            await _load(db, FacilityLocation, lid, org_id, "Location")
            db.add(FacilityLocationTag(facility_id=f.id, location_id=lid, org_id=org_id))
    if manager_ids is not None:
        await db.execute(delete(FacilityManagerLink).where(FacilityManagerLink.facility_id == f.id))
        for uid in manager_ids:
            await _load(db, User, uid, org_id, "User")
            db.add(FacilityManagerLink(facility_id=f.id, user_id=uid, org_id=org_id))


@router.get("/facilities", response_model=list[FacilityResponse], dependencies=[_read])
async def list_facilities(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(Facility).where(Facility.org_id == current_user.org_id, Facility.is_deleted == False).order_by(Facility.name))).scalars().all()  # noqa: E712
    return [await _facility_dict(db, f, current_user.org_id) for f in rows]


@router.post("/facilities", response_model=FacilityResponse, status_code=201, dependencies=[_write])
async def create_facility(payload: FacilityCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.facility_type_id:
        await _load(db, FacilityType, payload.facility_type_id, current_user.org_id, "Type")
    f = Facility(name=payload.name, facility_type_id=payload.facility_type_id, quantity=payload.quantity,
                 notes=payload.notes, is_active=payload.is_active, org_id=current_user.org_id)
    db.add(f)
    await db.flush()
    await _set_facility_links(db, f, current_user.org_id, payload.location_ids, payload.manager_ids)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_CREATED, "Facility", f.id, f.name, request)
    return await _facility_dict(db, f, current_user.org_id)


@router.patch("/facilities/{facility_id}", response_model=FacilityResponse, dependencies=[_write])
async def update_facility(facility_id: str, payload: FacilityUpdate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = await _load(db, Facility, facility_id, current_user.org_id, "Facility")
    data = payload.model_dump(exclude_unset=True)
    location_ids = data.pop("location_ids", None)
    manager_ids = data.pop("manager_ids", None)
    if data.get("facility_type_id"):
        await _load(db, FacilityType, data["facility_type_id"], current_user.org_id, "Type")
    for k, v in data.items():
        setattr(f, k, v)
    await _set_facility_links(db, f, current_user.org_id, location_ids, manager_ids)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_UPDATED, "Facility", f.id, f.name, request)
    return await _facility_dict(db, f, current_user.org_id)


@router.delete("/facilities/{facility_id}", status_code=204, dependencies=[_write])
async def delete_facility(facility_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    f = await _load(db, Facility, facility_id, current_user.org_id, "Facility")
    f.is_deleted = True
    f.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_DELETED, "Facility", f.id, f.name, request, severity="warning")


# ── Complaints ───────────────────────────────────────────────────────────────

async def _complaint_dict(db, c, fac_names, user_names):
    insp = (await db.execute(select(func.count(FacilityInspection.id)).where(FacilityInspection.complaint_id == c.id))).scalar() or 0
    return ComplaintResponse(
        id=c.id, reference=c.reference, title=c.title, description=c.description, facility_id=c.facility_id,
        facility_name=fac_names.get(c.facility_id), status=c.status, lodged_by=c.lodged_by,
        lodger_name=user_names.get(c.lodged_by), date_lodged=c.date_lodged, inspection_count=insp,
        org_id=c.org_id, created_at=c.created_at)


@router.get("/complaints", response_model=list[ComplaintResponse], dependencies=[_read])
async def list_complaints(mine: bool = False, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(FacilityComplaint).where(FacilityComplaint.org_id == current_user.org_id)
    if mine:
        q = q.where(FacilityComplaint.lodged_by == current_user.id)
    rows = (await db.execute(q.order_by(FacilityComplaint.created_at.desc()))).scalars().all()
    fac = await _facility_names(db, current_user.org_id, {r.facility_id for r in rows})
    usr = await _user_names(db, current_user.org_id, {r.lodged_by for r in rows})
    return [await _complaint_dict(db, c, fac, usr) for c in rows]


@router.post("/complaints", response_model=ComplaintResponse, status_code=201, dependencies=[_write])
async def create_complaint(payload: ComplaintCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.status not in _COMPLAINT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_COMPLAINT_STATUSES)}")
    if payload.facility_id:
        await _load(db, Facility, payload.facility_id, current_user.org_id, "Facility")
    c = FacilityComplaint(reference=_ref("FC"), title=payload.title, description=payload.description,
                          facility_id=payload.facility_id, status=payload.status, lodged_by=current_user.id,
                          date_lodged=payload.date_lodged or date.today(), org_id=current_user.org_id)
    db.add(c)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_CREATED, "FacilityComplaint", c.id, f"lodged complaint {c.reference}", request)
    fac = await _facility_names(db, current_user.org_id, {c.facility_id})
    usr = await _user_names(db, current_user.org_id, {c.lodged_by})
    return await _complaint_dict(db, c, fac, usr)


@router.patch("/complaints/{complaint_id}", response_model=ComplaintResponse, dependencies=[_write])
async def update_complaint(complaint_id: str, payload: ComplaintUpdate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _load(db, FacilityComplaint, complaint_id, current_user.org_id, "Complaint")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] not in _COMPLAINT_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")
    for k, v in data.items():
        setattr(c, k, v)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_UPDATED, "FacilityComplaint", c.id, f"complaint {c.reference}", request)
    fac = await _facility_names(db, current_user.org_id, {c.facility_id})
    usr = await _user_names(db, current_user.org_id, {c.lodged_by})
    return await _complaint_dict(db, c, fac, usr)


@router.delete("/complaints/{complaint_id}", status_code=204, dependencies=[_write])
async def delete_complaint(complaint_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _load(db, FacilityComplaint, complaint_id, current_user.org_id, "Complaint")
    await db.delete(c)
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_DELETED, "FacilityComplaint", complaint_id, f"complaint {c.reference}", request, severity="warning")


# ── Inspections ──────────────────────────────────────────────────────────────

@router.get("/inspections", response_model=list[InspectionResponse], dependencies=[_read])
async def list_inspections(mine: bool = False, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(FacilityInspection).where(FacilityInspection.org_id == current_user.org_id)
    if mine:
        q = q.where(FacilityInspection.inspector_id == current_user.id)
    rows = (await db.execute(q.order_by(FacilityInspection.created_at.desc()))).scalars().all()
    fac = await _facility_names(db, current_user.org_id, {r.facility_id for r in rows})
    usr = await _user_names(db, current_user.org_id, {r.inspector_id for r in rows})
    return [InspectionResponse(id=r.id, facility_id=r.facility_id, facility_name=fac.get(r.facility_id),
                               inspector_id=r.inspector_id, inspector_name=usr.get(r.inspector_id),
                               complaint_id=r.complaint_id, comment=r.comment, outcome=r.outcome,
                               inspection_date=r.inspection_date, org_id=r.org_id, created_at=r.created_at) for r in rows]


@router.post("/inspections", response_model=InspectionResponse, status_code=201, dependencies=[_write])
async def create_inspection(payload: InspectionCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.facility_id:
        await _load(db, Facility, payload.facility_id, current_user.org_id, "Facility")
    if payload.complaint_id:
        c = await _load(db, FacilityComplaint, payload.complaint_id, current_user.org_id, "Complaint")
        if c.status == "open":
            c.status = "in_progress"
    r = FacilityInspection(facility_id=payload.facility_id, inspector_id=current_user.id, complaint_id=payload.complaint_id,
                           comment=payload.comment, outcome=payload.outcome,
                           inspection_date=payload.inspection_date or date.today(), org_id=current_user.org_id)
    db.add(r)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_CREATED, "FacilityInspection", r.id, "recorded inspection", request)
    fac = await _facility_names(db, current_user.org_id, {r.facility_id})
    usr = await _user_names(db, current_user.org_id, {r.inspector_id})
    return InspectionResponse(id=r.id, facility_id=r.facility_id, facility_name=fac.get(r.facility_id),
                              inspector_id=r.inspector_id, inspector_name=usr.get(r.inspector_id),
                              complaint_id=r.complaint_id, comment=r.comment, outcome=r.outcome,
                              inspection_date=r.inspection_date, org_id=r.org_id, created_at=r.created_at)


@router.delete("/inspections/{inspection_id}", status_code=204, dependencies=[_write])
async def delete_inspection(inspection_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, FacilityInspection, inspection_id, current_user.org_id, "Inspection")
    await db.delete(r)


# ── Maintenance ──────────────────────────────────────────────────────────────

def _maint_dict(m, fac_names, user_names) -> MaintenanceResponse:
    return MaintenanceResponse(id=m.id, facility_id=m.facility_id, facility_name=fac_names.get(m.facility_id),
                               complaint_id=m.complaint_id, maintenance_type=m.maintenance_type, comment=m.comment,
                               total_cost=m.total_cost, status=m.status, requested_by=m.requested_by,
                               requester_name=user_names.get(m.requested_by), request_date=m.request_date,
                               org_id=m.org_id, created_at=m.created_at)


@router.get("/maintenance", response_model=list[MaintenanceResponse], dependencies=[_read])
async def list_maintenance(mine: bool = False, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(FacilityMaintenance).where(FacilityMaintenance.org_id == current_user.org_id)
    if mine:
        q = q.where(FacilityMaintenance.requested_by == current_user.id)
    rows = (await db.execute(q.order_by(FacilityMaintenance.created_at.desc()))).scalars().all()
    fac = await _facility_names(db, current_user.org_id, {r.facility_id for r in rows})
    usr = await _user_names(db, current_user.org_id, {r.requested_by for r in rows})
    return [_maint_dict(m, fac, usr) for m in rows]


@router.post("/maintenance", response_model=MaintenanceResponse, status_code=201, dependencies=[_write])
async def create_maintenance(payload: MaintenanceCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.facility_id:
        await _load(db, Facility, payload.facility_id, current_user.org_id, "Facility")
    if payload.complaint_id:
        await _load(db, FacilityComplaint, payload.complaint_id, current_user.org_id, "Complaint")
    m = FacilityMaintenance(facility_id=payload.facility_id, complaint_id=payload.complaint_id,
                            maintenance_type=payload.maintenance_type, comment=payload.comment,
                            total_cost=payload.total_cost, requested_by=current_user.id,
                            request_date=payload.request_date or date.today(), org_id=current_user.org_id)
    db.add(m)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_CREATED, "FacilityMaintenance", m.id, "requested maintenance", request)
    fac = await _facility_names(db, current_user.org_id, {m.facility_id})
    usr = await _user_names(db, current_user.org_id, {m.requested_by})
    return _maint_dict(m, fac, usr)


@router.patch("/maintenance/{maint_id}", response_model=MaintenanceResponse, dependencies=[_write])
async def update_maintenance(maint_id: str, payload: MaintenanceUpdate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    m = await _load(db, FacilityMaintenance, maint_id, current_user.org_id, "Maintenance")
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") and data["status"] not in _MAINT_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(_MAINT_STATUSES)}")
    for k, v in data.items():
        setattr(m, k, v)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_UPDATED, "FacilityMaintenance", m.id, f"maintenance → {m.status}", request)
    fac = await _facility_names(db, current_user.org_id, {m.facility_id})
    usr = await _user_names(db, current_user.org_id, {m.requested_by})
    return _maint_dict(m, fac, usr)


# ── Approval levels ──────────────────────────────────────────────────────────

async def _approval_dict(db, lv, names):
    return ApprovalLevelResponse(id=lv.id, name=lv.name, threshold=lv.threshold, handler_id=lv.handler_id,
                                 handler_name=names.get(lv.handler_id), is_active=lv.is_active, position=lv.position, org_id=lv.org_id)


@router.get("/approval-levels", response_model=list[ApprovalLevelResponse], dependencies=[_read])
async def list_approval_levels(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    rows = (await db.execute(select(FacilityApprovalLevel).where(FacilityApprovalLevel.org_id == current_user.org_id).order_by(FacilityApprovalLevel.threshold))).scalars().all()
    names = await _user_names(db, current_user.org_id, {r.handler_id for r in rows})
    return [await _approval_dict(db, lv, names) for lv in rows]


@router.post("/approval-levels", response_model=ApprovalLevelResponse, status_code=201, dependencies=[_write])
async def create_approval_level(payload: ApprovalLevelCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.handler_id:
        await _load(db, User, payload.handler_id, current_user.org_id, "Handler")
    lv = FacilityApprovalLevel(**payload.model_dump(), org_id=current_user.org_id)
    db.add(lv)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {lv.handler_id})
    return await _approval_dict(db, lv, names)


@router.patch("/approval-levels/{level_id}", response_model=ApprovalLevelResponse, dependencies=[_write])
async def update_approval_level(level_id: str, payload: ApprovalLevelUpdate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    lv = await _load(db, FacilityApprovalLevel, level_id, current_user.org_id, "Approval level")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(lv, k, v)
    await db.flush()
    names = await _user_names(db, current_user.org_id, {lv.handler_id})
    return await _approval_dict(db, lv, names)


@router.delete("/approval-levels/{level_id}", status_code=204, dependencies=[_write])
async def delete_approval_level(level_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    lv = await _load(db, FacilityApprovalLevel, level_id, current_user.org_id, "Approval level")
    await db.delete(lv)


# ── Requisitions ─────────────────────────────────────────────────────────────

async def _resolve_level(db, org_id, cost: Decimal):
    """The active approval level whose threshold the cost meets (highest ≤ cost)."""
    rows = (await db.execute(select(FacilityApprovalLevel).where(
        FacilityApprovalLevel.org_id == org_id, FacilityApprovalLevel.is_active == True,  # noqa: E712
        FacilityApprovalLevel.threshold <= cost).order_by(FacilityApprovalLevel.threshold.desc()))).scalars().all()
    return rows[0] if rows else None


async def _req_dict(db, r, names, level_names):
    return RequisitionResponse(id=r.id, reference=r.reference, title=r.title, maintenance_id=r.maintenance_id,
                               maintenance_type=r.maintenance_type, maintenance_cost=r.maintenance_cost,
                               requisition_cost=r.requisition_cost, status=r.status, approval_level_id=r.approval_level_id,
                               approval_level_name=level_names.get(r.approval_level_id), total_approved=r.total_approved,
                               approval_date=r.approval_date, total_disbursed=r.total_disbursed, requested_by=r.requested_by,
                               requester_name=names.get(r.requested_by), approved_by=r.approved_by, org_id=r.org_id, created_at=r.created_at)


async def _req_level_names(db, org_id, ids):
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = (await db.execute(select(FacilityApprovalLevel.id, FacilityApprovalLevel.name).where(FacilityApprovalLevel.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


@router.get("/requisitions", response_model=list[RequisitionResponse], dependencies=[_read])
async def list_requisitions(mine: bool = False, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    q = select(FacilityRequisition).where(FacilityRequisition.org_id == current_user.org_id)
    if mine:
        q = q.where(FacilityRequisition.requested_by == current_user.id)
    rows = (await db.execute(q.order_by(FacilityRequisition.created_at.desc()))).scalars().all()
    names = await _user_names(db, current_user.org_id, {r.requested_by for r in rows})
    lvls = await _req_level_names(db, current_user.org_id, {r.approval_level_id for r in rows})
    return [await _req_dict(db, r, names, lvls) for r in rows]


@router.post("/requisitions", response_model=RequisitionResponse, status_code=201, dependencies=[_write])
async def create_requisition(payload: RequisitionCreate, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    if payload.maintenance_id:
        await _load(db, FacilityMaintenance, payload.maintenance_id, current_user.org_id, "Maintenance")
    level = await _resolve_level(db, current_user.org_id, payload.requisition_cost)
    r = FacilityRequisition(reference=_ref("FR"), title=payload.title, maintenance_id=payload.maintenance_id,
                            maintenance_type=payload.maintenance_type, maintenance_cost=payload.maintenance_cost,
                            requisition_cost=payload.requisition_cost, status="pending",
                            approval_level_id=level.id if level else None, requested_by=current_user.id, org_id=current_user.org_id)
    db.add(r)
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_CREATED, "FacilityRequisition", r.id, f"raised requisition {r.reference}", request)
    names = await _user_names(db, current_user.org_id, {r.requested_by})
    lvls = await _req_level_names(db, current_user.org_id, {r.approval_level_id})
    return await _req_dict(db, r, names, lvls)


@router.post("/requisitions/{req_id}/approve", response_model=RequisitionResponse, dependencies=[_write])
async def approve_requisition(req_id: str, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, FacilityRequisition, req_id, current_user.org_id, "Requisition")
    if r.status not in ("pending", "draft"):
        raise HTTPException(status_code=409, detail=f"Cannot approve a requisition that is {r.status}.")
    r.status = "approved"
    r.total_approved = r.requisition_cost
    r.approval_date = date.today()
    r.approved_by = current_user.id
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_UPDATED, "FacilityRequisition", r.id, f"approved requisition {r.reference}", request, severity="warning")
    names = await _user_names(db, current_user.org_id, {r.requested_by})
    lvls = await _req_level_names(db, current_user.org_id, {r.approval_level_id})
    return await _req_dict(db, r, names, lvls)


@router.post("/requisitions/{req_id}/disburse", response_model=RequisitionResponse, dependencies=[_write])
async def disburse_requisition(req_id: str, payload: DisburseInput, request: Request = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    r = await _load(db, FacilityRequisition, req_id, current_user.org_id, "Requisition")
    if r.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved requisition can be disbursed.")
    amount = payload.amount if payload.amount is not None else r.total_approved
    r.total_disbursed = amount
    r.status = "disbursed"
    # NOTE: posting the spend to the general ledger reuses the finance ledger
    # service and sets journal_entry_id — wired as a follow-up (see module notes).
    await db.flush()
    await _audit(db, current_user.org_id, current_user, AuditAction.RECORD_UPDATED, "FacilityRequisition", r.id, f"disbursed {amount} on {r.reference}", request, severity="warning")
    names = await _user_names(db, current_user.org_id, {r.requested_by})
    lvls = await _req_level_names(db, current_user.org_id, {r.approval_level_id})
    return await _req_dict(db, r, names, lvls)


# ── Report ───────────────────────────────────────────────────────────────────

@router.get("/report", dependencies=[_read])
async def facility_report(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    org = current_user.org_id
    async def _count(model, *where):
        return (await db.execute(select(func.count(model.id)).where(model.org_id == org, *where))).scalar() or 0

    fac_total = await _count(Facility, Facility.is_deleted == False)  # noqa: E712
    complaints_total = await _count(FacilityComplaint)
    pending_complaints = await _count(FacilityComplaint, FacilityComplaint.status.in_(["open", "in_progress"]))
    maint_total = await _count(FacilityMaintenance)
    approved_req = await _count(FacilityRequisition, FacilityRequisition.status.in_(["approved", "disbursed"]))

    # by facility type
    type_rows = (await db.execute(
        select(FacilityType.name, func.count(Facility.id))
        .join(Facility, Facility.facility_type_id == FacilityType.id)
        .where(Facility.org_id == org, Facility.is_deleted == False)  # noqa: E712
        .group_by(FacilityType.name))).all()
    # expenses by approval level
    exp_rows = (await db.execute(
        select(FacilityApprovalLevel.name,
               func.coalesce(func.sum(FacilityRequisition.requisition_cost), 0),
               func.coalesce(func.sum(FacilityRequisition.total_approved), 0))
        .join(FacilityRequisition, FacilityRequisition.approval_level_id == FacilityApprovalLevel.id, isouter=True)
        .where(FacilityApprovalLevel.org_id == org)
        .group_by(FacilityApprovalLevel.name))).all()

    return {
        "cards": {"facilities": fac_total, "complaints": complaints_total, "maintenance": maint_total, "approved_requisitions": approved_req},
        "pending_complaints": pending_complaints,
        "by_type": [{"name": r[0], "count": r[1]} for r in type_rows],
        "expenses_by_level": [{"level": r[0], "total": float(r[1]), "approved": float(r[2])} for r in exp_rows],
    }


# ── Audit Trail (filtered view over the GLOBAL AuditLog) ─────────────────────

_AUDIT_CATEGORIES = {
    "facility": "Facility", "complaints": "FacilityComplaint", "inspection": "FacilityInspection",
    "maintenance": "FacilityMaintenance", "requisition": "FacilityRequisition",
}


@router.get("/audit", dependencies=[_read])
async def facility_audit(category: str | None = None, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """Filtered view of the global audit log for facility resource types — NOT a
    separate audit store. `category` narrows to one workflow stage."""
    rtypes = [_AUDIT_CATEGORIES[category]] if category in _AUDIT_CATEGORIES else FACILITY_RESOURCE_TYPES
    rows = (await db.execute(
        select(AuditLog).where(AuditLog.org_id == current_user.org_id, AuditLog.resource_type.in_(rtypes))
        .order_by(AuditLog.created_at.desc()).limit(200))).scalars().all()
    names = await _user_names(db, current_user.org_id, {a.actor_id for a in rows if getattr(a, "actor_id", None)})
    return {"items": [{
        "id": a.id,
        "full_name": names.get(getattr(a, "actor_id", None)),
        "activity": getattr(a, "resource_label", None) or (a.action.value if hasattr(a.action, "value") else str(a.action)),
        "resource_type": a.resource_type,
        "date": a.created_at.isoformat() if a.created_at else None,
    } for a in rows]}
