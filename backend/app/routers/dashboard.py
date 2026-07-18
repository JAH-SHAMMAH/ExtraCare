"""
Executive Dashboard Router (Phase 6.8)

Single endpoint that returns everything an owner/admin needs to feel in
control of the school at a glance. The whole response is structured as
flat primitives + small dicts so it serialises cleanly into Redis when
we wrap it in a cache layer (`@cache(ttl=30)` on the function below).

All counts are scoped to the caller's org. Admin-only — we don't want
teachers seeing whole-school SMS/transport aggregates.
"""

from datetime import date, datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.role import Role, user_roles
from app.models.organization import Organization
from app.models.modules.school import (
    Student, SchoolClass, AttendanceRecord, AttendanceStatus,
)
from app.models.modules.business import Employee, InventoryItem, FinanceTransaction, TransactionType
from app.models.modules.hospital import Patient, Appointment, AppointmentStatus, MedicalInvoice, InvoiceStatus
from app.models.modules.transport import (
    TransportTrip, TripBoarding, TripStatus, BoardingStatus,
)
from app.models.sms import (
    SmsCampaign, SmsMessage, SmsCampaignStatus, SmsMessageStatus,
)
from app.core.tenant import require_role_module
from app.core.school_identity import teacher_identity_filter
from app.core.permissions import PermissionChecker
from app.core.workspace import effective_modules_for_org, workspace_for


router = APIRouter(
    prefix="/dashboard",
    tags=["Executive Dashboard"],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_analytics_read = Depends(PermissionChecker("analytics:read"))

ADMIN_SLUGS = {"org_admin", "manager", "super_admin"}


def _is_admin(user: User) -> bool:
    return user.is_superadmin or any(r.slug in ADMIN_SLUGS for r in user.roles)


@router.get("/overview", dependencies=[Depends(require_role_module("school")), _can_read])
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """One-shot executive overview. Designed for caching:
      - Pure-input function (org_id + today's date are the only varying inputs)
      - Flat JSON-serialisable response
      - 30-second TTL is comfortable for the "control centre" use case

    Boundary enforcement:
      - Module gate: require_role_module("school") on the router
      - Permission gate: school:read
      - Role gate: admin/manager only — teachers don't see whole-school aggregates
    """
    if not _is_admin(current_user):
        raise HTTPException(403, detail="Only administrators can view the executive dashboard")

    org_id = current_user.org_id
    today = date.today()

    # ── Students: one GROUP BY for total + male + female ────────────────────
    # We deliberately group on lower(gender) to merge "Male"/"male"/"M" if any
    # legacy rows are mis-cased. Filter is_active=True so the headline number
    # matches "students currently enrolled" not historical roster.
    student_rows = (await db.execute(
        select(func.lower(Student.gender), func.count(Student.id))
        .where(
            Student.org_id == org_id,
            Student.is_deleted == False,
            Student.is_active == True,
        )
        .group_by(func.lower(Student.gender))
    )).all()
    male = 0
    female = 0
    other_or_unspecified = 0
    for g, n in student_rows:
        n = int(n)
        if g in ("male", "m"):
            male += n
        elif g in ("female", "f"):
            female += n
        else:
            other_or_unspecified += n
    total_students = male + female + other_or_unspecified

    # ── Classes ─────────────────────────────────────────────────────────────
    classes_count = (await db.execute(
        select(func.count(SchoolClass.id)).where(SchoolClass.org_id == org_id)
    )).scalar_one() or 0

    # ── Teachers: users identified as teachers by the app's convention (job_title
    # contains "teacher"). Matches the Teachers list exactly, and — unlike the old
    # 'teacher' role-slug join — counts subject teachers ("Physics Teacher", …),
    # who never carry that role in practice.
    teachers_count = (await db.execute(
        select(func.count(User.id)).where(
            User.org_id == org_id,
            User.is_deleted == False,  # noqa: E712
            teacher_identity_filter(),
        )
    )).scalar_one() or 0

    # ── Attendance today: count of present + late marks ────────────────────
    attendance_today = (await db.execute(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.org_id == org_id,
            AttendanceRecord.date == today,
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE]),
        )
    )).scalar_one() or 0

    # Yesterday's attendance — used to surface the +/- delta on the card.
    # One extra COUNT; cheap.
    yesterday = today - timedelta(days=1)
    attendance_yesterday = (await db.execute(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.org_id == org_id,
            AttendanceRecord.date == yesterday,
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE]),
        )
    )).scalar_one() or 0

    # ── Transport: trips by status today, on-board now, issues ─────────────
    trip_rows = (await db.execute(
        select(TransportTrip.status, func.count(TransportTrip.id))
        .where(
            TransportTrip.org_id == org_id,
            TransportTrip.trip_date == today,
        )
        .group_by(TransportTrip.status)
    )).all()
    trip_counts: dict[str, int] = {}
    for st, n in trip_rows:
        key = st.value if hasattr(st, "value") else str(st)
        trip_counts[key] = int(n)
    active_trips = trip_counts.get(TripStatus.IN_PROGRESS.value, 0)

    # On-board now: BOARDED rows attached to today's IN_PROGRESS trips.
    students_on_board = (await db.execute(
        select(func.count(TripBoarding.id))
        .select_from(TripBoarding)
        .join(TransportTrip, TransportTrip.id == TripBoarding.trip_id)
        .where(
            TripBoarding.org_id == org_id,
            TripBoarding.status == BoardingStatus.BOARDED,
            TransportTrip.trip_date == today,
            TransportTrip.status == TripStatus.IN_PROGRESS,
        )
    )).scalar_one() or 0

    # Issues today: skipped boardings + cancelled trips + trips running long.
    # Skipped count and cancelled trips done via a single GROUP BY each;
    # "running long" is computed in Python from started_at.
    skipped_today = (await db.execute(
        select(func.count(TripBoarding.id))
        .select_from(TripBoarding)
        .join(TransportTrip, TransportTrip.id == TripBoarding.trip_id)
        .where(
            TripBoarding.org_id == org_id,
            TripBoarding.status == BoardingStatus.SKIPPED,
            TransportTrip.trip_date == today,
        )
    )).scalar_one() or 0
    cancelled_today = trip_counts.get(TripStatus.CANCELLED.value, 0)

    long_running = 0
    if active_trips:
        in_progress_trips = (await db.execute(
            select(TransportTrip.started_at).where(
                TransportTrip.org_id == org_id,
                TransportTrip.trip_date == today,
                TransportTrip.status == TripStatus.IN_PROGRESS,
            )
        )).scalars().all()
        now = datetime.now(timezone.utc)
        for started in in_progress_trips:
            if not started:
                continue
            # SQLite returns naive datetimes — pin to UTC before subtracting.
            s = started if started.tzinfo else started.replace(tzinfo=timezone.utc)
            if (now - s).total_seconds() / 60 > 90:
                long_running += 1

    transport_issues = int(skipped_today) + int(cancelled_today) + long_running

    # ── SMS today: aggregate counts on campaigns created today. ────────────
    # We sum the denormalised counters on SmsCampaign rather than walking
    # SmsMessage to keep this single-query and aligned with how the SMS
    # router itself reports state.
    sms_row = (await db.execute(
        select(
            func.coalesce(func.sum(SmsCampaign.sent_count), 0),
            func.coalesce(func.sum(SmsCampaign.delivered_count), 0),
            func.coalesce(func.sum(SmsCampaign.failed_count), 0),
            func.count(SmsCampaign.id),
        ).where(
            SmsCampaign.org_id == org_id,
            func.date(SmsCampaign.created_at) == today,
        )
    )).one()
    sent_today = int(sms_row[0] or 0)
    delivered_today = int(sms_row[1] or 0)
    failed_today = int(sms_row[2] or 0)
    campaigns_today = int(sms_row[3] or 0)

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "students": {
            "total": total_students,
            "male": male,
            "female": female,
            "other": other_or_unspecified,
        },
        "classes": int(classes_count),
        "teachers": int(teachers_count),
        "attendance_today": int(attendance_today),
        "transport": {
            "active_trips": active_trips,
            "students_on_board": int(students_on_board),
            "issues": transport_issues,
            # Sub-breakdown so the UI can show "1 cancelled · 2 skipped" if
            # the issue count is non-zero — better than just a vague tally.
            "issue_breakdown": {
                "skipped": int(skipped_today),
                "cancelled": int(cancelled_today),
                "running_long": long_running,
            },
            "trips_planned": trip_counts.get(TripStatus.PLANNED.value, 0),
            "trips_completed": trip_counts.get(TripStatus.COMPLETED.value, 0),
        },
        "sms": {
            "campaigns_today": campaigns_today,
            "sent_today": sent_today,
            "delivered_today": delivered_today,
            "failed_today": failed_today,
        },
    }


@router.get("/workspace-overview", dependencies=[_can_analytics_read])
async def workspace_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Workspace-aware dashboard contract used by the shared product shell.

    Unlike /dashboard/overview, this endpoint is not school-specific. It
    returns cards and quick actions only for the caller's active workspace.
    """
    org = (await db.execute(
        select(Organization).where(Organization.id == current_user.org_id)
    )).scalar_one_or_none()
    if not org:
        raise HTTPException(400, detail="Tenant not resolved.")

    modules = set(effective_modules_for_org(org))
    workspace = workspace_for(org.industry.value if org.industry else None)
    today = date.today()

    if "school" in modules:
        cards = await _school_workspace_cards(db, current_user.org_id, today)
        quick_actions = [
            {"label": "New Student", "href": "/dashboard/modules/school/students?new=1", "module": "school"},
            {"label": "Mark Attendance", "href": "/dashboard/modules/school/attendance", "module": "school"},
            {"label": "Create Exam", "href": "/dashboard/modules/school/exams?new=1", "module": "school"},
            {"label": "HR Manager", "href": "/dashboard/hrm", "module": "hr"},
        ]
    elif "hospital" in modules:
        cards = await _hospital_workspace_cards(db, current_user.org_id, today)
        quick_actions = [
            {"label": "New Patient", "href": "/dashboard/modules/hospital/patients?new=1", "module": "hospital"},
            {"label": "Book Appointment", "href": "/dashboard/modules/hospital/appointments?new=1", "module": "hospital"},
            {"label": "Medical Records", "href": "/dashboard/modules/hospital/records", "module": "hospital"},
            {"label": "HR Manager", "href": "/dashboard/hrm", "module": "hr"},
        ]
    elif "business" in modules:
        cards = await _business_workspace_cards(db, current_user.org_id, today)
        quick_actions = [
            {"label": "New Employee", "href": "/dashboard/modules/business/employees?new=1", "module": "business"},
            {"label": "Inventory", "href": "/dashboard/modules/business/inventory", "module": "business"},
            {"label": "Finance", "href": "/dashboard/modules/business/finance", "module": "finance"},
            {"label": "HR Manager", "href": "/dashboard/hrm", "module": "hr"},
        ]
    else:
        cards = []
        quick_actions = [{"label": "Enable Modules", "href": "/dashboard/settings", "module": "platform"}]

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "workspace": {
            "type": workspace.type.value,
            "label": workspace.label,
            "dashboard_type": workspace.dashboard_type,
            "modules_enabled": sorted(modules),
        },
        "cards": cards,
        "quick_actions": quick_actions,
    }


async def _school_workspace_cards(db: AsyncSession, org_id: str, today: date) -> list[dict[str, Any]]:
    students = int((await db.execute(
        select(func.count(Student.id)).where(
            Student.org_id == org_id,
            Student.is_deleted == False,
            Student.is_active == True,
        )
    )).scalar() or 0)
    classes = int((await db.execute(
        select(func.count(SchoolClass.id)).where(SchoolClass.org_id == org_id)
    )).scalar() or 0)
    attendance = int((await db.execute(
        select(func.count(AttendanceRecord.id)).where(
            AttendanceRecord.org_id == org_id,
            AttendanceRecord.date == today,
            AttendanceRecord.status.in_([AttendanceStatus.PRESENT, AttendanceStatus.LATE]),
        )
    )).scalar() or 0)
    teachers = int((await db.execute(
        select(func.count(User.id)).where(
            User.org_id == org_id, User.is_deleted == False, teacher_identity_filter(),  # noqa: E712
        )
    )).scalar() or 0)
    return [
        {"label": "Active Students", "value": students, "sub": "Currently enrolled", "href": "/dashboard/modules/school/students"},
        {"label": "Classes", "value": classes, "sub": "Academic groups", "href": "/dashboard/modules/school/classes"},
        {"label": "Teachers", "value": teachers, "sub": "Teaching staff", "href": "/dashboard/modules/school/teachers"},
        {"label": "Attendance Today", "value": attendance, "sub": "Present or late marks", "href": "/dashboard/modules/school/attendance"},
    ]


async def _business_workspace_cards(db: AsyncSession, org_id: str, today: date) -> list[dict[str, Any]]:
    employees = int((await db.execute(
        select(func.count(Employee.id)).where(Employee.org_id == org_id, Employee.is_deleted == False)
    )).scalar() or 0)
    inventory = int((await db.execute(
        select(func.count(InventoryItem.id)).where(InventoryItem.org_id == org_id, InventoryItem.is_deleted == False)
    )).scalar() or 0)
    low_stock_items = (await db.execute(
        select(InventoryItem.quantity_in_stock, InventoryItem.reorder_level).where(
            InventoryItem.org_id == org_id,
            InventoryItem.is_deleted == False,
        )
    )).all()
    low_stock = sum(1 for qty, reorder in low_stock_items if (qty or 0) <= (reorder or 0))
    month_start = today.replace(day=1)
    finance_rows = (await db.execute(
        select(FinanceTransaction.type, func.coalesce(func.sum(FinanceTransaction.amount), 0))
        .where(
            FinanceTransaction.org_id == org_id,
            FinanceTransaction.is_deleted == False,
            FinanceTransaction.transaction_date >= month_start,
        )
        .group_by(FinanceTransaction.type)
    )).all()
    totals = {t.value if hasattr(t, "value") else str(t): float(v or 0) for t, v in finance_rows}
    revenue = totals.get(TransactionType.INCOME.value, 0.0)
    expenses = totals.get(TransactionType.EXPENSE.value, 0.0)
    return [
        {"label": "Employees", "value": employees, "sub": "Active company records", "href": "/dashboard/modules/business/employees"},
        {"label": "Inventory Items", "value": inventory, "sub": f"{low_stock} below reorder", "href": "/dashboard/modules/business/inventory"},
        {"label": "Revenue This Month", "value": round(revenue, 2), "sub": "Recorded income", "href": "/dashboard/modules/business/finance"},
        {"label": "Expenses This Month", "value": round(expenses, 2), "sub": "Recorded expenses", "href": "/dashboard/modules/business/finance"},
    ]


async def _hospital_workspace_cards(db: AsyncSession, org_id: str, today: date) -> list[dict[str, Any]]:
    patients = int((await db.execute(
        select(func.count(Patient.id)).where(Patient.org_id == org_id, Patient.is_deleted == False)
    )).scalar() or 0)
    appointments_today = int((await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.org_id == org_id,
            Appointment.appointment_date == today,
            Appointment.status.in_([AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED, AppointmentStatus.IN_PROGRESS]),
        )
    )).scalar() or 0)
    records_today = int((await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.org_id == org_id,
            Appointment.appointment_date == today,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    )).scalar() or 0)
    open_bills = int((await db.execute(
        select(func.count(MedicalInvoice.id)).where(
            MedicalInvoice.org_id == org_id,
            MedicalInvoice.status.in_([InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.OVERDUE]),
        )
    )).scalar() or 0)
    return [
        {"label": "Patients", "value": patients, "sub": "Active patient records", "href": "/dashboard/modules/hospital/patients"},
        {"label": "Appointments Today", "value": appointments_today, "sub": "Scheduled or in progress", "href": "/dashboard/modules/hospital/appointments"},
        {"label": "Visits Completed", "value": records_today, "sub": "Completed today", "href": "/dashboard/modules/hospital/records"},
        {"label": "Open Bills", "value": open_bills, "sub": "Draft, sent, or overdue", "href": "/dashboard/modules/hospital/billing"},
    ]
