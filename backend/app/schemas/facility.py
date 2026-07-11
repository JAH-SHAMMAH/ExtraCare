"""Schemas for the Facility Management module."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Lookups (types / locations / departments) ────────────────────────────────

class NameCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class NameUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)


class LookupResponse(_Orm):
    id: str
    name: str
    org_id: str


class DepartmentResponse(_Orm):
    id: str
    name: str
    org_id: str
    officer_count: int = 0


# ── Facilities ───────────────────────────────────────────────────────────────

class FacilityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    facility_type_id: Optional[str] = None
    quantity: int = Field(default=1, ge=0)
    notes: Optional[str] = None
    is_active: bool = True
    location_ids: Optional[list[str]] = None
    manager_ids: Optional[list[str]] = None


class FacilityUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    facility_type_id: Optional[str] = None
    quantity: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    location_ids: Optional[list[str]] = None
    manager_ids: Optional[list[str]] = None


class FacilityResponse(_Orm):
    id: str
    name: str
    facility_type_id: Optional[str]
    facility_type_name: Optional[str] = None
    quantity: int
    notes: Optional[str]
    is_active: bool
    location_ids: list[str] = []
    location_names: list[str] = []
    manager_ids: list[str] = []
    manager_names: list[str] = []
    inspection_count: int = 0
    org_id: str
    created_at: datetime


# ── Facility staff / role pools ──────────────────────────────────────────────

_STAFF_ROLES = {"facility_manager", "requisition_manager", "store_keeper", "officer"}


class StaffCreate(BaseModel):
    user_id: str
    role_type: str
    department_id: Optional[str] = None


class StaffResponse(_Orm):
    id: str
    user_id: str
    user_name: Optional[str] = None
    role_type: str
    department_id: Optional[str]
    org_id: str


# ── Complaints ───────────────────────────────────────────────────────────────

_COMPLAINT_STATUSES = {"open", "in_progress", "resolved", "closed"}


class ComplaintCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    facility_id: Optional[str] = None
    status: str = "open"
    date_lodged: Optional[date] = None


class ComplaintUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    facility_id: Optional[str] = None
    status: Optional[str] = None


class ComplaintResponse(_Orm):
    id: str
    reference: str
    title: str
    description: Optional[str]
    facility_id: Optional[str]
    facility_name: Optional[str] = None
    status: str
    lodged_by: Optional[str]
    lodger_name: Optional[str] = None
    date_lodged: Optional[date]
    inspection_count: int = 0
    org_id: str
    created_at: datetime


# ── Inspections ──────────────────────────────────────────────────────────────

class InspectionCreate(BaseModel):
    facility_id: Optional[str] = None
    complaint_id: Optional[str] = None
    comment: Optional[str] = None
    outcome: Optional[str] = None
    inspection_date: Optional[date] = None


class InspectionUpdate(BaseModel):
    facility_id: Optional[str] = None
    complaint_id: Optional[str] = None
    comment: Optional[str] = None
    outcome: Optional[str] = None
    inspection_date: Optional[date] = None


class InspectionResponse(_Orm):
    id: str
    facility_id: Optional[str]
    facility_name: Optional[str] = None
    inspector_id: Optional[str]
    inspector_name: Optional[str] = None
    complaint_id: Optional[str]
    comment: Optional[str]
    outcome: Optional[str]
    inspection_date: Optional[date]
    org_id: str
    created_at: datetime


# ── Maintenance ──────────────────────────────────────────────────────────────

_MAINT_STATUSES = {"pending", "approved", "in_progress", "completed", "rejected"}


class MaintenanceCreate(BaseModel):
    facility_id: Optional[str] = None
    complaint_id: Optional[str] = None
    maintenance_type: Optional[str] = None
    comment: Optional[str] = None
    total_cost: Decimal = Decimal("0")
    request_date: Optional[date] = None


class MaintenanceUpdate(BaseModel):
    facility_id: Optional[str] = None
    complaint_id: Optional[str] = None
    maintenance_type: Optional[str] = None
    comment: Optional[str] = None
    total_cost: Optional[Decimal] = None
    status: Optional[str] = None


class MaintenanceResponse(_Orm):
    id: str
    facility_id: Optional[str]
    facility_name: Optional[str] = None
    complaint_id: Optional[str]
    maintenance_type: Optional[str]
    comment: Optional[str]
    total_cost: Decimal
    status: str
    requested_by: Optional[str]
    requester_name: Optional[str] = None
    request_date: Optional[date]
    org_id: str
    created_at: datetime


# ── Approval levels ──────────────────────────────────────────────────────────

class ApprovalLevelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    threshold: Decimal = Decimal("0")
    handler_id: Optional[str] = None
    is_active: bool = True
    position: int = 0


class ApprovalLevelUpdate(BaseModel):
    name: Optional[str] = None
    threshold: Optional[Decimal] = None
    handler_id: Optional[str] = None
    is_active: Optional[bool] = None
    position: Optional[int] = None


class ApprovalLevelResponse(_Orm):
    id: str
    name: str
    threshold: Decimal
    handler_id: Optional[str]
    handler_name: Optional[str] = None
    is_active: bool
    position: int
    org_id: str


# ── Requisitions ─────────────────────────────────────────────────────────────

class RequisitionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    maintenance_id: Optional[str] = None
    maintenance_type: Optional[str] = None
    maintenance_cost: Decimal = Decimal("0")
    requisition_cost: Decimal = Decimal("0")


class RequisitionUpdate(BaseModel):
    title: Optional[str] = None
    maintenance_type: Optional[str] = None
    maintenance_cost: Optional[Decimal] = None
    requisition_cost: Optional[Decimal] = None


class DisburseInput(BaseModel):
    amount: Optional[Decimal] = None   # defaults to total_approved


class RequisitionResponse(_Orm):
    id: str
    reference: str
    title: str
    maintenance_id: Optional[str]
    maintenance_type: Optional[str]
    maintenance_cost: Decimal
    requisition_cost: Decimal
    status: str
    approval_level_id: Optional[str]
    approval_level_name: Optional[str] = None
    total_approved: Decimal
    approval_date: Optional[date]
    total_disbursed: Decimal
    requested_by: Optional[str]
    requester_name: Optional[str] = None
    approved_by: Optional[str]
    org_id: str
    created_at: datetime
