from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, datetime, timezone

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.hospital import Patient, Appointment, MedicalRecord, MedicalInvoice, AppointmentStatus
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker

router = APIRouter(
    prefix="/hospital",
    tags=["Hospital Module"],
    dependencies=[Depends(require_role_module("hospital"))],
)

_can_read = Depends(PermissionChecker("hospital:read"))
_can_write = Depends(PermissionChecker("hospital:write"))


# ── Patients ──────────────────────────────────────────────────────────────────

@router.get("/patients", dependencies=[_can_read])
async def list_patients(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Patient).where(Patient.org_id == current_user.org_id, Patient.is_deleted == False)
    if search:
        term = f"%{search}%"
        query = query.where(
            Patient.first_name.ilike(term) | Patient.last_name.ilike(term) | Patient.patient_id.ilike(term)
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    patients = result.scalars().all()

    return {"items": [_patient_dict(p) for p in patients], "total": total}


@router.post("/patients", status_code=201, dependencies=[_can_write])
async def register_patient(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    patient = Patient(**{k: v for k, v in data.items() if k not in ("org_id", "id")}, org_id=current_user.org_id)
    db.add(patient)
    await db.flush()
    return _patient_dict(patient)


# ── Appointments ──────────────────────────────────────────────────────────────

@router.get("/appointments", dependencies=[_can_read])
async def list_appointments(
    appointment_date: date | None = None,
    doctor_id: str | None = None,
    status: AppointmentStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Appointment).where(Appointment.org_id == current_user.org_id)
    if appointment_date:
        query = query.where(Appointment.appointment_date == appointment_date)
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if status:
        query = query.where(Appointment.status == status)

    result = await db.execute(query.order_by(Appointment.appointment_date, Appointment.start_time))
    return [_appt_dict(a) for a in result.scalars().all()]


@router.post("/appointments", status_code=201, dependencies=[_can_write])
async def book_appointment(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    appt = Appointment(**{k: v for k, v in data.items() if k not in ("org_id", "id")}, org_id=current_user.org_id)
    db.add(appt)
    await db.flush()
    return _appt_dict(appt)


@router.patch("/appointments/{appt_id}/status", dependencies=[_can_write])
async def update_appointment_status(
    appt_id: str,
    new_status: AppointmentStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Appointment).where(Appointment.id == appt_id, Appointment.org_id == current_user.org_id)
    )
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    appt.status = new_status
    return _appt_dict(appt)


# ── Medical Records ───────────────────────────────────────────────────────────

@router.post("/records", status_code=201, dependencies=[_can_write])
async def create_medical_record(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    record = MedicalRecord(
        **{k: v for k, v in data.items() if k not in ("org_id", "id", "doctor_id")},
        doctor_id=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(record)
    await db.flush()
    return {"id": record.id, "patient_id": record.patient_id, "visit_date": str(record.visit_date)}


@router.get("/patients/{patient_id}/history", dependencies=[_can_read])
async def patient_medical_history(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(MedicalRecord).where(
            MedicalRecord.patient_id == patient_id,
            MedicalRecord.org_id == current_user.org_id,
        ).order_by(MedicalRecord.visit_date.desc())
    )
    return [
        {
            "id": r.id,
            "visit_date": str(r.visit_date),
            "diagnosis": r.diagnosis,
            "treatment_plan": r.treatment_plan,
            "vitals": r.vitals,
            "prescriptions": r.prescriptions,
        }
        for r in result.scalars().all()
    ]


def _patient_dict(p: Patient) -> dict:
    return {
        "id": p.id, "patient_id": p.patient_id,
        "first_name": p.first_name, "last_name": p.last_name,
        "email": p.email, "phone": p.phone,
        "blood_type": p.blood_type.value if p.blood_type else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _appt_dict(a: Appointment) -> dict:
    return {
        "id": a.id, "patient_id": a.patient_id, "doctor_id": a.doctor_id,
        "appointment_date": str(a.appointment_date),
        "start_time": a.start_time, "end_time": a.end_time,
        "status": a.status.value, "reason": a.reason,
    }
