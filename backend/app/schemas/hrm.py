"""Pydantic schemas for the HR module.

Design notes:
* ``HRProfileUpdate`` uses ``exclude_unset=True`` upstream so omitting a
  field is "no change" and explicit ``null`` is "clear it". That lets the
  UI send partial patches and the user to blank out a field intentionally.
* ``HRProfileResponse`` is what every viewer sees. Sensitive fields
  (salary, bank_account_number) are served either masked or omitted based
  on the viewer's permission — the router decides, not the schema.
* Blank-string coercion is the same pattern used in `student.py` /
  `teacher.py`: HTML forms submit ``""`` for unfilled optional fields and
  SQLAlchemy ``Date``/``Float`` columns reject that at flush.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, field_validator


def _empty_to_none(v):
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


# ── HR Profile ───────────────────────────────────────────────────────────────

_OPTIONAL_STR_FIELDS = (
    "title", "first_name", "middle_name", "surname", "staff_id",
    "employment_status", "gender", "marital_status", "nationality",
    "national_id", "address",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
    "salary_currency", "bank_name", "bank_account_name", "bank_account_number",
    "pension_provider", "pension_id",
)
_OPTIONAL_DATE_FIELDS = ("date_of_birth", "national_id_expiry", "hire_date")


class HRProfileUpdate(BaseModel):
    # Personal
    title: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    surname: Optional[str] = None
    staff_id: Optional[str] = None
    employment_status: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None

    # Identification
    national_id: Optional[str] = None
    national_id_expiry: Optional[date] = None

    # Contact
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None

    # Employment
    hire_date: Optional[date] = None

    # Salary & pension
    salary: Optional[float] = None
    salary_currency: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    pension_provider: Optional[str] = None
    pension_id: Optional[str] = None

    # Memberships + family
    memberships: Optional[list[dict[str, Any]]] = None
    next_of_kin: Optional[dict[str, Any]] = None
    dependents: Optional[list[dict[str, Any]]] = None

    @field_validator(*(_OPTIONAL_STR_FIELDS + _OPTIONAL_DATE_FIELDS), mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return _empty_to_none(v)

    @field_validator("salary", mode="before")
    @classmethod
    def _salary_blank_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class HRProfileResponse(BaseModel):
    id: str
    user_id: str
    org_id: str

    # Identity (some fields duplicated from User for one-shot render)
    email: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None

    # Personal
    title: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    surname: Optional[str] = None
    staff_id: Optional[str] = None
    employment_status: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None

    # Identification
    national_id: Optional[str] = None
    national_id_expiry: Optional[date] = None

    # Contact
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None

    # Employment
    hire_date: Optional[date] = None

    # Salary — always a number/None; `bank_account_number` comes masked for
    # non-admin viewers (set router-side).
    salary: Optional[float] = None
    salary_currency: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    pension_provider: Optional[str] = None
    pension_id: Optional[str] = None

    memberships: list[dict[str, Any]] = []
    next_of_kin: dict[str, Any] = {}
    dependents: list[dict[str, Any]] = []

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ── Events ───────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    category: Optional[str] = None

    @field_validator("description", "location", "category", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return _empty_to_none(v)

    @field_validator("title", mode="before")
    @classmethod
    def _title_not_blank(cls, v):
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("must not be blank")
        return v


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    category: Optional[str] = None

    @field_validator("description", "location", "category", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return _empty_to_none(v)


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    starts_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    category: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None


# ── Birthdays & Overview ─────────────────────────────────────────────────────

class BirthdayItem(BaseModel):
    name: str
    role: str                    # "staff" | "student"
    date_of_birth: date
    is_today: bool
    days_until: int              # 0 = today, else days ahead within month window


class DepartmentCount(BaseModel):
    department: str
    count: int


class CategoryCount(BaseModel):
    label: str
    count: int


class HROverview(BaseModel):
    total_active_staff: int
    total_profiles: int
    staff_per_department: list[DepartmentCount]
    gender_distribution: list[CategoryCount]
    age_distribution: list[CategoryCount]
