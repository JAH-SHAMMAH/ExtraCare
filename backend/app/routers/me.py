"""
/me — Personalisation Endpoints
================================
Resolves the authenticated user to their school-side identity (student or
teacher) so the frontend can render personalised dashboards without holding
linkage logic on the client.

Resolution strategy (no dedicated student/teacher auth roles yet):
  - Student   → match Student.email == User.email within the same org.
  - Teacher   → User is referenced by SchoolClass.teacher_id, Subject.teacher_id
                or Timetable.teacher_id within the same org.

A user can be both (rare but possible). The persona the frontend chooses is
still driven by RBAC (school:write etc.) — this endpoint just provides the
linked entities and the IDs that feed `for_me` filters elsewhere.
"""

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    Student,
    SchoolClass,
    Subject,
    Timetable,
    ParentGuardian,
    AttendanceRecord,
    AttendanceStatus,
    Grade,
    Assignment,
)
from app.core.tenant import require_module
from app.core.events import log_event

router = APIRouter(
    prefix="/me",
    tags=["Me"],
)


@router.get("/school-context", dependencies=[Depends(require_module("school"))])
async def school_context(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Per-user linkage changes rarely (admin-triggered). Private cache for 60s
    # is a safe nudge for browser + React Query; never shared between users.
    response.headers["Cache-Control"] = "private, max-age=60"
    """
    Returns the linked Student record (if any) and the classes/subjects this
    user teaches (if any). Frontends use this to drive `for_me=true` queries
    without round-tripping to figure out the linked IDs themselves.
    """
    student = None
    if current_user.email:
        result = await db.execute(
            select(Student).where(
                Student.email == current_user.email,
                Student.org_id == current_user.org_id,
                Student.is_deleted == False,
            )
        )
        student_row = result.scalar_one_or_none()
        if student_row:
            student = {
                "id": student_row.id,
                "student_id": student_row.student_id,
                "first_name": student_row.first_name,
                "last_name": student_row.last_name,
                "class_id": student_row.class_id,
                "photo_url": student_row.photo_url,
            }

    classes_result = await db.execute(
        select(SchoolClass).where(
            SchoolClass.teacher_id == current_user.id,
            SchoolClass.org_id == current_user.org_id,
        )
    )
    classes = [
        {"id": c.id, "name": c.name, "level": c.level, "academic_year": c.academic_year}
        for c in classes_result.scalars().all()
    ]

    subjects_result = await db.execute(
        select(Subject).where(
            Subject.teacher_id == current_user.id,
            Subject.org_id == current_user.org_id,
        )
    )
    subjects = [
        {"id": s.id, "name": s.name, "code": s.code}
        for s in subjects_result.scalars().all()
    ]

    is_teacher = bool(classes or subjects)

    # Resolution telemetry — used to spot misconfigured tenants where most
    # users land unlinked. Email mismatches are the usual culprit.
    log_event(
        "school_context_resolved",
        org_id=current_user.org_id,
        user_id=current_user.id,
        student_linked=student is not None,
        teacher_linked=is_teacher,
        unlinked=(student is None and not is_teacher),
    )

    return {
        "user_id": current_user.id,
        "student": student,
        "is_teacher": is_teacher,
        "classes": classes,
        "subjects": subjects,
    }


# ── Phase 6.3: Multi-role contexts ───────────────────────────────────────────
#
# One endpoint powers the role switcher + every role-scoped home page. All
# scoping is done SERVER-SIDE from the authenticated user's identity; the
# frontend never sends "which role am I" to the backend for data-fetch
# purposes (it only uses activeRole to pick which section of the response
# to render). 


async def _resolve_student_row(db: AsyncSession, user: User) -> Student | None:
    """Find the Student record for this user. Prefers the explicit FK added in
    Phase 6.3; falls back to the legacy email match so orgs seeded pre-6.3
    don't break."""
    if user.email:
        # Prefer FK. Fall back to email match scoped to the same org.
        fk_match = (await db.execute(
            select(Student).where(
                Student.user_id == user.id,
                Student.org_id == user.org_id,
                Student.is_deleted == False,
            )
        )).scalar_one_or_none()
        if fk_match:
            return fk_match
        email_match = (await db.execute(
            select(Student).where(
                Student.email == user.email,
                Student.org_id == user.org_id,
                Student.is_deleted == False,
            )
        )).scalar_one_or_none()
        return email_match
    return None


def _serialize_class(c: SchoolClass) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "level": c.level,
        "academic_year": c.academic_year,
        "room": c.room,
    }


def _serialize_subject(s: Subject) -> dict[str, Any]:
    return {"id": s.id, "name": s.name, "code": s.code}


def _serialize_slot(t: Timetable, subject_name: str | None) -> dict[str, Any]:
    return {
        "id": t.id,
        "class_id": t.class_id,
        "subject_id": t.subject_id,
        "subject_name": subject_name,
        "day_of_week": t.day_of_week,
        "start_time": t.start_time,
        "end_time": t.end_time,
        "room": t.room,
        "teacher_id": t.teacher_id,
    }


async def _teacher_context(db: AsyncSession, user: User) -> dict[str, Any] | None:
    form_classes = (await db.execute(
        select(SchoolClass).where(
            SchoolClass.teacher_id == user.id,
            SchoolClass.org_id == user.org_id,
        )
    )).scalars().all()
    subjects = (await db.execute(
        select(Subject).where(
            Subject.teacher_id == user.id,
            Subject.org_id == user.org_id,
        )
    )).scalars().all()

    # Subject teachers don't own the class (that's the form teacher's role)
    # but they need it surfaced so the Lesson Planner can target it, the
    # "My Classes" page is non-empty, etc. Broaden classes to include every
    # class the teacher meets via a timetable slot they own.
    slot_class_ids = (await db.execute(
        select(Timetable.class_id).where(
            Timetable.teacher_id == user.id,
            Timetable.org_id == user.org_id,
        ).distinct()
    )).scalars().all()
    extra_class_ids = [cid for cid in slot_class_ids if cid and cid not in {c.id for c in form_classes}]
    extra_classes = []
    if extra_class_ids:
        extra_classes = (await db.execute(
            select(SchoolClass).where(
                SchoolClass.id.in_(extra_class_ids),
                SchoolClass.org_id == user.org_id,
            )
        )).scalars().all()
    classes = list(form_classes) + list(extra_classes)

    if not classes and not subjects:
        return None

    # Teacher's timetable: slots they personally teach OR slots belonging to
    # their form class (so a form teacher sees the whole class's week at a
    # glance, not just their own lessons).
    form_class_ids = [c.id for c in form_classes]
    slot_rows = (await db.execute(
        select(Timetable, Subject.name).outerjoin(
            Subject, Subject.id == Timetable.subject_id,
        ).where(
            Timetable.org_id == user.org_id,
            ((Timetable.teacher_id == user.id) | (Timetable.class_id.in_(form_class_ids) if form_class_ids else False)),
        )
    )).all()
    slots = [_serialize_slot(t, name) for (t, name) in slot_rows]

    # Pending grades — unpublished grade rows the teacher owns via subject.
    pending_grades = 0
    if subjects:
        pending_grades = (await db.execute(
            select(func.count(Grade.id)).where(
                Grade.org_id == user.org_id,
                Grade.subject_id.in_([s.id for s in subjects]),
                Grade.status == "draft",
            )
        )).scalar_one() or 0

    # Build today's slots from the teacher's OWN slots (not the form class's
    # entire day) — the "today lessons" stat on the teacher home should count
    # what THEY are teaching today, not what their class has scheduled.
    today_idx = date.today().weekday()
    own_today = [
        s for s in slots
        if s["day_of_week"] == today_idx and (s["teacher_id"] == user.id or not form_class_ids)
    ]
    own_today.sort(key=lambda s: s["start_time"] or "")

    return {
        "classes": [_serialize_class(c) for c in classes],
        "subjects": [_serialize_subject(s) for s in subjects],
        "timetable": slots,
        "today_slots": own_today,
        "stats": {
            "classes_count": len(classes),
            "subjects_count": len(subjects),
            "today_lessons": len(own_today),
            "pending_grades": int(pending_grades),
        },
    }


async def _student_context(db: AsyncSession, user: User, student: Student) -> dict[str, Any]:
    # Class + timetable
    school_class = None
    timetable: list[dict[str, Any]] = []
    if student.class_id:
        cls = (await db.execute(
            select(SchoolClass).where(SchoolClass.id == student.class_id)
        )).scalar_one_or_none()
        if cls:
            school_class = _serialize_class(cls)
        slot_rows = (await db.execute(
            select(Timetable, Subject.name).outerjoin(
                Subject, Subject.id == Timetable.subject_id,
            ).where(
                Timetable.class_id == student.class_id,
                Timetable.org_id == user.org_id,
            )
        )).all()
        timetable = sorted(
            [_serialize_slot(t, name) for (t, name) in slot_rows],
            key=lambda s: (s["day_of_week"], s["start_time"] or ""),
        )

    # Attendance this term (rough: last 60 days). For demo, "this month" is
    # clear enough for a parent/student.
    since = date.today() - timedelta(days=60)
    att_rows = (await db.execute(
        select(AttendanceRecord.status, func.count(AttendanceRecord.id)).where(
            AttendanceRecord.student_id == student.id,
            AttendanceRecord.org_id == user.org_id,
            AttendanceRecord.date >= since,
        ).group_by(AttendanceRecord.status)
    )).all()
    att_counts: dict[str, int] = {}
    for status, n in att_rows:
        key = status.value if hasattr(status, "value") else str(status)
        att_counts[key] = int(n)
    att_total = sum(att_counts.values())
    att_present = att_counts.get("present", 0) + att_counts.get("late", 0)
    att_pct = round((att_present / att_total) * 100) if att_total else None

    # Pending assignments (published, not yet past due).
    pending_assignments = 0
    if student.class_id:
        pending_assignments = (await db.execute(
            select(func.count(Assignment.id)).where(
                Assignment.org_id == user.org_id,
                Assignment.class_id == student.class_id,
                Assignment.status == "published",
                Assignment.is_deleted == False,
            )
        )).scalar_one() or 0

    today_idx = date.today().weekday()
    today_slots = [s for s in timetable if s["day_of_week"] == today_idx]

    return {
        "student": {
            "id": student.id,
            "student_id": student.student_id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "photo_url": student.photo_url,
            "class_id": student.class_id,
        },
        "class": school_class,
        "timetable": timetable,
        "today_slots": today_slots,
        "stats": {
            "attendance_pct": att_pct,
            "attendance_days": att_total,
            "pending_assignments": int(pending_assignments),
        },
    }


async def _parent_context(db: AsyncSession, user: User) -> dict[str, Any] | None:
    """Return children + per-child snapshot stats for a parent user."""
    links = (await db.execute(
        select(ParentGuardian).where(
            ParentGuardian.user_id == user.id,
            ParentGuardian.org_id == user.org_id,
        )
    )).scalars().all()
    if not links:
        return None

    student_ids = [l.student_id for l in links]
    students = (await db.execute(
        select(Student).where(
            Student.id.in_(student_ids),
            Student.is_deleted == False,
        )
    )).scalars().all()
    students_by_id = {s.id: s for s in students}

    # Per-child snapshot: attendance% (last 60d), pending assignments count,
    # latest grade letter. Kept to simple aggregates so the dashboard stays
    # snappy without pulling full histories.
    since = date.today() - timedelta(days=60)
    children: list[dict[str, Any]] = []
    for link in links:
        stu = students_by_id.get(link.student_id)
        if not stu:
            continue

        att_rows = (await db.execute(
            select(AttendanceRecord.status, func.count(AttendanceRecord.id)).where(
                AttendanceRecord.student_id == stu.id,
                AttendanceRecord.org_id == user.org_id,
                AttendanceRecord.date >= since,
            ).group_by(AttendanceRecord.status)
        )).all()
        att_counts: dict[str, int] = {}
        for status, n in att_rows:
            key = status.value if hasattr(status, "value") else str(status)
            att_counts[key] = int(n)
        att_total = sum(att_counts.values())
        att_present = att_counts.get("present", 0) + att_counts.get("late", 0)
        att_pct = round((att_present / att_total) * 100) if att_total else None

        pending_assignments = 0
        if stu.class_id:
            pending_assignments = (await db.execute(
                select(func.count(Assignment.id)).where(
                    Assignment.org_id == user.org_id,
                    Assignment.class_id == stu.class_id,
                    Assignment.status == "published",
                    Assignment.is_deleted == False,
                )
            )).scalar_one() or 0

        latest_grade = (await db.execute(
            select(Grade).where(
                Grade.student_id == stu.id,
                Grade.status == "published",
            ).order_by(Grade.created_at.desc()).limit(1)
        )).scalar_one_or_none()

        class_name = None
        if stu.class_id:
            cls = (await db.execute(
                select(SchoolClass).where(SchoolClass.id == stu.class_id)
            )).scalar_one_or_none()
            class_name = cls.name if cls else None

        children.append({
            "id": stu.id,
            "student_id": stu.student_id,
            "first_name": stu.first_name,
            "last_name": stu.last_name,
            "photo_url": stu.photo_url,
            "class_id": stu.class_id,
            "class_name": class_name,
            "relationship": link.relationship_type,
            "is_primary": link.is_primary,
            "stats": {
                "attendance_pct": att_pct,
                "pending_assignments": int(pending_assignments),
                "latest_grade_letter": latest_grade.grade_letter if latest_grade else None,
                "latest_grade_score": latest_grade.score if latest_grade else None,
            },
        })

    return {"children": children}


@router.get("/contexts", dependencies=[Depends(require_module("school"))])
async def contexts(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Single endpoint powering the role switcher + all four role-scoped home
    dashboards. Returns one section per role the user can assume; nulls for
    roles that don't apply. Short private cache — role linkage changes rarely.
    """
    response.headers["Cache-Control"] = "private, max-age=30"

    role_slugs = {r.slug for r in current_user.roles}
    has_admin_role = bool(role_slugs & {"org_admin", "manager", "super_admin"}) or current_user.is_superadmin

    # Student context (resolved via FK or email fallback).
    student_row = await _resolve_student_row(db, current_user)
    as_student = await _student_context(db, current_user, student_row) if student_row else None

    # Teacher context (classes/subjects owned).
    as_teacher = await _teacher_context(db, current_user)

    # Parent context (via ParentGuardian links).
    as_parent = await _parent_context(db, current_user)

    # Derive the set of "real" roles this user can switch into, based on actual
    # data linkage rather than only role slugs. This means a teacher who is
    # also a parent can switch to parent view even if the role was never
    # explicitly assigned — the data IS the identity.
    available: list[str] = []
    if has_admin_role:
        available.append("admin")
    if as_teacher:
        available.append("teacher")
    if as_parent:
        available.append("parent")
    if as_student:
        available.append("student")

    # Default role = the most privileged they have.
    default_role = next((r for r in ("admin", "teacher", "parent", "student") if r in available), "admin")

    log_event(
        "me_contexts_resolved",
        org_id=current_user.org_id,
        user_id=current_user.id,
        available_roles=available,
        default_role=default_role,
    )

    return {
        "user_id": current_user.id,
        "roles": sorted(role_slugs),
        "available_roles": available,
        "default_role": default_role,
        "as_admin": {"is_admin": True} if has_admin_role else None,
        "as_teacher": as_teacher,
        "as_parent": as_parent,
        "as_student": as_student,
    }
