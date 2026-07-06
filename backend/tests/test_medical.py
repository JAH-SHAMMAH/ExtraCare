"""Tests for the CONFIDENTIAL Medicals surface (Batch 4).

The headline requirement: a regular teacher/staff CANNOT read medical records;
only org_admin + the nurse (health officer) can. The `medical:*` namespace sits
OUTSIDE the broad `school:read` hierarchy, which these tests assert directly
(has_permission is exactly what the PermissionChecker gate evaluates).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.pastoral import StudentMedicalRecord
from app.routers.modules.medical import (
    list_medical_records, create_medical_record, update_medical_record, delete_medical_record,
)
from app.schemas.medical import MedicalRecordCreate, MedicalRecordUpdate


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


# ── RBAC: the core confidentiality contract ───────────────────────────────────

async def test_teacher_cannot_read_or_write_medical(db, org):
    teacher = await _preset_user(db, org, "teacher")
    assert teacher.has_permission("school:read") is True       # broad school access…
    assert teacher.has_permission("medical:read") is False     # …does NOT reach medical
    assert teacher.has_permission("medical:write") is False


async def test_staff_and_low_trust_cannot_read_medical(db, org):
    for slug in ("staff", "manager", "viewer", "student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("medical:read"), f"{slug} must NOT read medical"
        assert not u.has_permission("medical:write"), f"{slug} must NOT write medical"


async def test_nurse_and_admin_can_access_medical(db, org):
    nurse = await _preset_user(db, org, "nurse")
    assert nurse.has_permission("medical:read") is True
    assert nurse.has_permission("medical:write") is True
    # The nurse is scoped to medical ONLY — no general school access.
    assert nurse.has_permission("school:read") is False
    assert nurse.has_permission("school:students:read") is False

    admin = await _preset_user(db, org, "org_admin")
    assert admin.has_permission("medical:read") is True    # via medical:*
    assert admin.has_permission("medical:write") is True


# ── Functional CRUD (driven as the nurse) ──────────────────────────────────────

async def test_nurse_crud_medical_record(db, org, student):
    nurse = await _preset_user(db, org, "nurse")
    rec = await create_medical_record(
        MedicalRecordCreate(student_id=student.id, record_type="visit", title="Fever", severity="low"),
        request=None, db=db, current_user=nurse,
    )
    assert rec.recorded_by == nurse.id
    assert rec.student_name == "Ada Okafor"

    listing = await list_medical_records(student_id=None, record_type=None, page=1, page_size=25, db=db, current_user=nurse)
    assert listing.total == 1

    updated = await update_medical_record(rec.id, MedicalRecordUpdate(severity="high"), db=db, current_user=nurse)
    assert updated.severity == "high"

    await delete_medical_record(rec.id, request=None, db=db, current_user=nurse)
    assert (await list_medical_records(student_id=None, record_type=None, page=1, page_size=25, db=db, current_user=nurse)).total == 0


async def test_medical_validation_and_tenant_scope(db, org, student):
    nurse = await _preset_user(db, org, "nurse")
    with pytest.raises(HTTPException) as exc:
        await create_medical_record(MedicalRecordCreate(student_id=student.id, record_type="xray"),
                                    request=None, db=db, current_user=nurse)
    assert exc.value.status_code == 422

    await create_medical_record(MedicalRecordCreate(student_id=student.id, record_type="note"),
                                request=None, db=db, current_user=nurse)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    nurse2 = User(id=str(uuid.uuid4()), email="n2@example.com", full_name="N2",
                  status=UserStatus.ACTIVE, org_id=other.id)
    db.add(nurse2)
    await db.commit()
    theirs = await list_medical_records(student_id=None, record_type=None, page=1, page_size=25, db=db, current_user=nurse2)
    assert theirs.total == 0
