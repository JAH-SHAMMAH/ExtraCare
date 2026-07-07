import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from datetime import date

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User, UserStatus
from app.models.modules.school import (
    Student, SchoolClass, AttendanceRecord, Grade, Subject, Timetable,
    LessonPlan, LessonPlanStatus, ParentGuardian,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.teacher import TeacherCreate, TeacherUpdate
from app.schemas.school_class import ClassCreate, ClassUpdate
from app.schemas.subject import SubjectCreate, SubjectUpdate

logger = logging.getLogger("extracare.school")

router = APIRouter(
    prefix="/school",
    tags=["School Module"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:read"))
_can_write = Depends(PermissionChecker("school:write"))
# Fine-grained scopes for student/parent-reachable reads. Broad `school:read`
# still satisfies these via the scope hierarchy, so admin/teacher/staff are
# unaffected; students and parents reach them with their narrow grants, and the
# per-record ownership check below stops them seeing anyone else's data.
_reports_read = Depends(PermissionChecker("school:reports:read"))
_attendance_read = Depends(PermissionChecker("school:attendance:read"))
_lessons_read = Depends(PermissionChecker("school:lessons:read"))


async def _user_owns_student(db: AsyncSession, user: User, student_id: str) -> bool:
    """True if `user` is the student themselves or one of their linked guardians."""
    own = (await db.execute(
        select(Student.id).where(
            Student.id == student_id,
            Student.org_id == user.org_id,
            Student.is_deleted == False,
            or_(Student.user_id == user.id, Student.email == user.email),
        )
    )).scalar_one_or_none()
    if own:
        return True
    link = (await db.execute(
        select(ParentGuardian.id).where(
            ParentGuardian.user_id == user.id,
            ParentGuardian.student_id == student_id,
            ParentGuardian.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    return link is not None


async def _ensure_student_visible(db: AsyncSession, user: User, student_id: str) -> None:
    """Authorize access to a single student's records.

    Staff-side roles — anyone whose grant covers `school:students:read` (admin,
    manager, teacher, staff, viewer via the broad `school:read`) — may view any
    student in their org. Students and parents are restricted to their own
    record / linked children; passing another student's id raises 403 so they
    can never enumerate or read peers' data.
    """
    if user.has_permission("school:students:read"):
        return
    if await _user_owns_student(db, user, student_id):
        return
    raise HTTPException(status_code=403, detail="You can only access your own records.")


# ── Students ──────────────────────────────────────────────────────────────────

@router.get("/students", dependencies=[_can_read])
async def list_students(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = None,
    class_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Student).where(
        Student.org_id == current_user.org_id,
        Student.is_deleted == False,
    )
    if search:
        term = f"%{search}%"
        query = query.where(
            Student.first_name.ilike(term) | Student.last_name.ilike(term) | Student.student_id.ilike(term)
        )
    if class_id:
        query = query.where(Student.class_id == class_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    students = result.scalars().all()

    return {
        "items": [_student_dict(s) for s in students],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/students", status_code=201, dependencies=[_can_write])
async def create_student(
    data: StudentCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    payload = data.model_dump()
    logger.info(
        "student_create.start org=%s actor=%s student_id=%s class_id=%s",
        org_id, current_user.id, payload["student_id"], payload.get("class_id"),
    )

    # If class_id was provided, confirm it belongs to this tenant before
    # the insert. Letting the FK fire at flush would 500 with a generic
    # error; this returns a specific message the UI can surface.
    if payload.get("class_id"):
        klass = (await db.execute(
            select(SchoolClass.id).where(
                SchoolClass.id == payload["class_id"],
                SchoolClass.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not klass:
            logger.warning(
                "student_create.class_not_found org=%s class_id=%s",
                org_id, payload["class_id"],
            )
            raise HTTPException(
                status_code=404,
                detail=f"Class not found for class_id: {payload['class_id']}",
            )

    student = Student(**payload, org_id=org_id)
    db.add(student)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        logger.warning(
            "student_create.integrity_error org=%s student_id=%s err=%s",
            org_id, payload["student_id"], e.orig,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Student with ID '{payload['student_id']}' could not be created (duplicate or FK violation).",
        )

    logger.info(
        "student_create.ok org=%s id=%s student_id=%s",
        org_id, student.id, student.student_id,
    )
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="Student", resource_id=student.id,
        resource_label=f"{student.first_name} {student.last_name}",
        new_values={"student_id": student.student_id, "class_id": student.class_id},
        request=request,
    )
    return _student_dict(student)


@router.patch("/students/{id}", dependencies=[_can_write])
async def update_student(
    id: str,
    data: StudentUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    result = await db.execute(
        select(Student).where(
            Student.id == id,
            Student.org_id == org_id,
            Student.is_deleted == False,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found for id: {id}")

    updates = data.model_dump(exclude_unset=True)
    if "class_id" in updates and updates["class_id"]:
        klass = (await db.execute(
            select(SchoolClass.id).where(
                SchoolClass.id == updates["class_id"],
                SchoolClass.org_id == org_id,
            )
        )).scalar_one_or_none()
        if not klass:
            raise HTTPException(
                status_code=404,
                detail=f"Class not found for class_id: {updates['class_id']}",
            )

    for key, value in updates.items():
        setattr(student, key, value)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        logger.warning("student_update.integrity_error org=%s id=%s err=%s", org_id, id, e.orig)
        raise HTTPException(status_code=409, detail="Student update conflicts with an existing record.")
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="Student", resource_id=student.id,
        resource_label=f"{student.first_name} {student.last_name}",
        new_values=updates, request=request,
    )
    return _student_dict(student)


@router.delete("/students/{id}", status_code=204, dependencies=[_can_write])
async def delete_student(
    id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Student).where(
            Student.id == id,
            Student.org_id == current_user.org_id,
            Student.is_deleted == False,
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail=f"Student not found for id: {id}")
    student.is_deleted = True
    from datetime import datetime, timezone
    student.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="Student", resource_id=student.id,
        resource_label=f"{student.first_name} {student.last_name}",
        severity="warning", request=request,
    )


# ── Classes ───────────────────────────────────────────────────────────────────
# The general class-list endpoint the frontend (`schoolApi.classes` / `useClasses`)
# has always expected. Its absence made class dropdowns render empty app-wide
# (enrollment, class pickers). Maps the ORM columns to the frontend `SchoolClass`
# shape: level->grade_level, max_capacity->capacity, teacher_id->class_teacher_id,
# with a resolved class_teacher_name + computed student_count.

async def _class_student_counts(db: AsyncSession, org_id: str, class_ids: list[str] | None = None) -> dict[str, int]:
    q = (
        select(Student.class_id, func.count(Student.id))
        .where(Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
        .group_by(Student.class_id)
    )
    if class_ids is not None:
        q = q.where(Student.class_id.in_(class_ids))
    return {cid: int(n) for cid, n in (await db.execute(q)).all() if cid}


async def _teacher_names(db: AsyncSession, org_id: str, teacher_ids: set[str]) -> dict[str, str]:
    ids = {t for t in teacher_ids if t}
    if not ids:
        return {}
    rows = (await db.execute(
        select(User.id, User.full_name).where(User.org_id == org_id, User.id.in_(ids))
    )).all()
    return {uid: name for uid, name in rows}


def _class_dict(c: SchoolClass, student_count: int, teacher_name: str | None) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "grade_level": c.level,
        "section": c.section,
        "class_teacher_id": c.teacher_id,
        "class_teacher_name": teacher_name,
        "capacity": int(c.max_capacity or 0),
        "student_count": student_count,
        "academic_year": c.academic_year or "",
        "is_active": True,   # SchoolClass has no soft-delete/active flag; always active
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def _load_class(db: AsyncSession, class_id: str, org_id: str) -> SchoolClass:
    c = (await db.execute(
        select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
    )).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail=f"Class not found for id: {class_id}")
    return c


async def _validate_teacher(db: AsyncSession, org_id: str, teacher_id: str | None) -> None:
    if not teacher_id:
        return
    ok = (await db.execute(
        select(User.id).where(User.id == teacher_id, User.org_id == org_id)
    )).scalar_one_or_none()
    if not ok:
        raise HTTPException(status_code=404, detail=f"Teacher not found for id: {teacher_id}")


@router.get("/classes", dependencies=[_can_read])
async def list_classes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(SchoolClass).where(SchoolClass.org_id == current_user.org_id)
    if search:
        term = f"%{search}%"
        query = query.where(
            SchoolClass.name.ilike(term) | SchoolClass.level.ilike(term) | SchoolClass.section.ilike(term)
        )
    query = query.order_by(SchoolClass.name)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    classes = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    counts = await _class_student_counts(db, current_user.org_id, [c.id for c in classes])
    names = await _teacher_names(db, current_user.org_id, {c.teacher_id for c in classes})
    return {
        "items": [_class_dict(c, counts.get(c.id, 0), names.get(c.teacher_id)) for c in classes],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/classes/{class_id}", dependencies=[_can_read])
async def get_class(class_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    c = await _load_class(db, class_id, current_user.org_id)
    counts = await _class_student_counts(db, current_user.org_id, [c.id])
    names = await _teacher_names(db, current_user.org_id, {c.teacher_id})
    return _class_dict(c, counts.get(c.id, 0), names.get(c.teacher_id))


@router.post("/classes", status_code=201, dependencies=[_can_write])
async def create_class(
    data: ClassCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    await _validate_teacher(db, org_id, data.class_teacher_id)
    c = SchoolClass(
        name=data.name, level=data.grade_level, section=data.section,
        academic_year=data.academic_year, teacher_id=data.class_teacher_id or None,
        room=data.room, max_capacity=data.capacity if data.capacity is not None else 40,
        org_id=org_id,
    )
    db.add(c)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="SchoolClass", resource_id=c.id, resource_label=c.name,
        new_values={"name": c.name, "level": c.level, "section": c.section}, request=request,
    )
    names = await _teacher_names(db, org_id, {c.teacher_id})
    return _class_dict(c, 0, names.get(c.teacher_id))


@router.patch("/classes/{class_id}", dependencies=[_can_write])
async def update_class(
    class_id: str,
    data: ClassUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    c = await _load_class(db, class_id, org_id)
    updates = data.model_dump(exclude_unset=True)
    if "class_teacher_id" in updates:
        await _validate_teacher(db, org_id, updates["class_teacher_id"])
    # Map frontend field names onto the ORM columns.
    field_map = {"grade_level": "level", "capacity": "max_capacity", "class_teacher_id": "teacher_id"}
    for field, value in updates.items():
        setattr(c, field_map.get(field, field), value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="SchoolClass", resource_id=c.id, resource_label=c.name,
        new_values={k: v for k, v in updates.items()}, request=request,
    )
    counts = await _class_student_counts(db, org_id, [c.id])
    names = await _teacher_names(db, org_id, {c.teacher_id})
    return _class_dict(c, counts.get(c.id, 0), names.get(c.teacher_id))


@router.delete("/classes/{class_id}", status_code=204, dependencies=[_can_write])
async def delete_class(
    class_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    c = await _load_class(db, class_id, org_id)
    # SchoolClass is hard-deleted (no soft-delete). Guard against orphaning students.
    enrolled = (await db.execute(
        select(func.count(Student.id)).where(
            Student.class_id == class_id, Student.org_id == org_id, Student.is_deleted == False)  # noqa: E712
    )).scalar() or 0
    if enrolled > 0:
        raise HTTPException(status_code=409, detail=f"Class still has {enrolled} student(s) — reassign them first.")
    label = c.name
    await db.delete(c)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, org_id, actor=current_user,
        resource_type="SchoolClass", resource_id=class_id, resource_label=label,
        severity="warning", request=request,
    )


# ── Subjects (curriculum) ──────────────────────────────────────────────────────

def _subject_dict(s: Subject) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "code": s.code or "",
        "department": s.department,
        "class_ids": [],   # subject↔class linkage not modelled yet; round-trips empty
        "teacher_id": s.teacher_id,
        "teacher_name": s.teacher_name,
        "credit_hours": int(s.credit_hours or 1),
        "is_active": bool(s.is_active),
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


async def _load_subject(db: AsyncSession, subject_id: str, org_id: str) -> Subject:
    s = (await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.org_id == org_id)
    )).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail=f"Subject not found for id: {subject_id}")
    return s


@router.get("/subjects", dependencies=[_can_read])
async def list_subjects(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Subject).where(Subject.org_id == current_user.org_id)
    if search:
        term = f"%{search}%"
        query = query.where(
            Subject.name.ilike(term) | Subject.code.ilike(term) | Subject.department.ilike(term)
        )
    query = query.order_by(Subject.name)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    subjects = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return {
        "items": [_subject_dict(s) for s in subjects],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/subjects/{subject_id}", dependencies=[_can_read])
async def get_subject(subject_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    return _subject_dict(await _load_subject(db, subject_id, current_user.org_id))


@router.post("/subjects", status_code=201, dependencies=[_can_write])
async def create_subject(
    data: SubjectCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    await _validate_teacher(db, org_id, data.teacher_id)
    s = Subject(
        name=data.name, code=data.code, department=data.department,
        credit_hours=data.credit_hours if data.credit_hours is not None else 1,
        is_active=data.is_active if data.is_active is not None else True,
        teacher_id=data.teacher_id or None, teacher_name=data.teacher_name, org_id=org_id,
    )
    db.add(s)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="Subject", resource_id=s.id, resource_label=s.name,
        new_values={"name": s.name, "code": s.code, "department": s.department}, request=request,
    )
    return _subject_dict(s)


@router.patch("/subjects/{subject_id}", dependencies=[_can_write])
async def update_subject(
    subject_id: str,
    data: SubjectUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    s = await _load_subject(db, subject_id, org_id)
    updates = data.model_dump(exclude_unset=True)
    if "teacher_id" in updates:
        await _validate_teacher(db, org_id, updates["teacher_id"])
    for field, value in updates.items():
        setattr(s, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="Subject", resource_id=s.id, resource_label=s.name,
        new_values=updates, request=request,
    )
    return _subject_dict(s)


@router.delete("/subjects/{subject_id}", status_code=204, dependencies=[_can_write])
async def delete_subject(
    subject_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    s = await _load_subject(db, subject_id, org_id)
    # Guard: subjects carry grades (Grade.subject_id FK). Block hard-delete if any exist.
    graded = (await db.execute(
        select(func.count(Grade.id)).where(Grade.subject_id == subject_id, Grade.org_id == org_id)
    )).scalar() or 0
    if graded > 0:
        raise HTTPException(status_code=409, detail=f"Subject has {graded} grade record(s) — cannot delete.")
    label = s.name
    await db.delete(s)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, org_id, actor=current_user,
        resource_type="Subject", resource_id=subject_id, resource_label=label,
        severity="warning", request=request,
    )


# ── Attendance ────────────────────────────────────────────────────────────────

@router.post("/attendance", dependencies=[_can_write])
async def mark_attendance(
    records: list[dict],  # [{"student_id": ..., "class_id": ..., "status": "present"}]
    attendance_date: date = Query(default=None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Bulk mark attendance for a class."""
    target_date = attendance_date or date.today()
    created = []
    for rec in records:
        obj = AttendanceRecord(
            student_id=rec["student_id"],
            class_id=rec["class_id"],
            date=target_date,
            status=rec.get("status", "present"),
            marked_by=current_user.id,
            org_id=current_user.org_id,
        )
        db.add(obj)
        created.append(rec["student_id"])
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="AttendanceRecord",
        resource_label=f"{len(created)} attendance record(s) for {target_date.isoformat()}",
        metadata={"count": len(created), "date": target_date.isoformat()},
        request=request,
    )
    return {"marked": len(created), "date": target_date.isoformat()}


@router.get("/attendance/summary", dependencies=[_can_read])
async def attendance_summary(
    class_id: str,
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(
            AttendanceRecord.status,
            func.count(AttendanceRecord.id).label("count")
        ).where(
            AttendanceRecord.org_id == current_user.org_id,
            AttendanceRecord.class_id == class_id,
            AttendanceRecord.date.between(start_date, end_date),
        ).group_by(AttendanceRecord.status)
    )
    summary = {row.status.value: row.count for row in result}
    total = sum(summary.values())
    return {
        "summary": summary,
        "total": total,
        "attendance_rate": round(summary.get("present", 0) / total * 100, 1) if total else 0,
    }


# ── Grades ────────────────────────────────────────────────────────────────────

@router.post("/grades", status_code=201, dependencies=[_can_write])
async def submit_grades(
    grades: list[dict],
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    created = []
    for g in grades:
        grade = Grade(
            student_id=g["student_id"],
            subject_id=g["subject_id"],
            score=g.get("score"),
            max_score=g.get("max_score", 100),
            term=g.get("term"),
            remarks=g.get("remarks"),
            graded_by=current_user.id,
            org_id=current_user.org_id,
        )
        db.add(grade)
        created.append(grade)
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Grade",
        resource_label=f"{len(created)} grade(s) submitted",
        severity="warning",
        metadata={"count": len(created)},
        request=request,
    )
    return {"submitted": len(created)}


@router.get("/students/{student_id}/report-card", dependencies=[_reports_read])
async def get_report_card(
    student_id: str,
    term: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _ensure_student_visible(db, current_user, student_id)
    query = select(Grade).where(
        Grade.student_id == student_id,
        Grade.org_id == current_user.org_id,
    )
    if term:
        query = query.where(Grade.term == term)

    result = await db.execute(query)
    grades = result.scalars().all()

    return {
        "student_id": student_id,
        "term": term,
        "grades": [
            {"subject_id": g.subject_id, "score": g.score, "max_score": g.max_score, "remarks": g.remarks}
            for g in grades
        ],
        "average": round(sum(g.score for g in grades if g.score) / len(grades), 2) if grades else 0,
    }


def _student_dict(s: Student) -> dict:
    return {
        "id": s.id,
        "student_id": s.student_id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "email": s.email,
        "class_id": s.class_id,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── Timetable ─────────────────────────────────────────────────────────────────


@router.get("/timetable", dependencies=[_can_read])
async def list_timetable(
    class_id: str | None = None,
    teacher_id: str | None = None,
    day_of_week: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Timetable).where(Timetable.org_id == current_user.org_id)
    if class_id:
        query = query.where(Timetable.class_id == class_id)
    if teacher_id:
        query = query.where(Timetable.teacher_id == teacher_id)
    if day_of_week is not None:
        query = query.where(Timetable.day_of_week == day_of_week)
    query = query.order_by(Timetable.day_of_week.asc(), Timetable.start_time.asc())
    items = (await db.execute(query)).scalars().all()
    return {"items": [_timetable_dict(t) for t in items]}


@router.post("/timetable", status_code=201, dependencies=[_can_write])
async def create_timetable_slot(
    data: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Strip client-supplied org_id/id so a tenant cannot plant records
    # into another organization or forge a primary key.
    payload = {k: v for k, v in data.items() if k not in ("org_id", "id")}
    slot = Timetable(**payload, org_id=current_user.org_id)
    db.add(slot)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Timetable", resource_id=slot.id,
        resource_label=f"class {slot.class_id} day {slot.day_of_week} {slot.start_time}",
        new_values={"class_id": slot.class_id, "subject_id": slot.subject_id, "teacher_id": slot.teacher_id},
        request=request,
    )
    return _timetable_dict(slot)


@router.patch("/timetable/{slot_id}", dependencies=[_can_write])
async def update_timetable_slot(
    slot_id: str,
    data: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Timetable).where(
            Timetable.id == slot_id,
            Timetable.org_id == current_user.org_id,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found.")

    for key, value in data.items():
        if key in ("org_id", "id"):
            continue
        setattr(slot, key, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Timetable", resource_id=slot.id,
        resource_label=f"class {slot.class_id} day {slot.day_of_week} {slot.start_time}",
        new_values={k: v for k, v in data.items() if k not in ("org_id", "id")},
        request=request,
    )
    return _timetable_dict(slot)


@router.delete("/timetable/{slot_id}", status_code=204, dependencies=[_can_write])
async def delete_timetable_slot(
    slot_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Timetable).where(
            Timetable.id == slot_id,
            Timetable.org_id == current_user.org_id,
        )
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Timetable slot not found.")
    slot_ref, slot_label = slot.id, f"class {slot.class_id} day {slot.day_of_week} {slot.start_time}"
    await db.delete(slot)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="Timetable", resource_id=slot_ref, resource_label=slot_label,
        severity="warning", request=request,
    )


def _timetable_dict(t: Timetable) -> dict:
    return {
        "id": t.id,
        "class_id": t.class_id,
        "subject_id": t.subject_id,
        "teacher_id": t.teacher_id,
        "day_of_week": t.day_of_week,
        "start_time": t.start_time,
        "end_time": t.end_time,
        "room": t.room,
    }


# ── Student Attendance History ────────────────────────────────────────────────


@router.get("/attendance/student/{student_id}", dependencies=[_attendance_read])
async def student_attendance_history(
    student_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Timeline view used by the student's own dashboard + pastoral reports."""
    await _ensure_student_visible(db, current_user, student_id)
    query = select(AttendanceRecord).where(
        AttendanceRecord.student_id == student_id,
        AttendanceRecord.org_id == current_user.org_id,
    )
    if start_date:
        query = query.where(AttendanceRecord.date >= start_date)
    if end_date:
        query = query.where(AttendanceRecord.date <= end_date)
    query = query.order_by(AttendanceRecord.date.desc())
    items = (await db.execute(query)).scalars().all()

    # Aggregate counts for a quick summary card in the UI.
    counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    for rec in items:
        key = rec.status.value if hasattr(rec.status, "value") else rec.status
        counts[key] = counts.get(key, 0) + 1
    total = sum(counts.values())

    return {
        "student_id": student_id,
        "records": [
            {
                "id": r.id,
                "date": r.date.isoformat() if r.date else None,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "class_id": r.class_id,
                "notes": r.notes,
            }
            for r in items
        ],
        "summary": {
            **counts,
            "total": total,
            "attendance_rate": round(counts.get("present", 0) / total * 100, 1) if total else 0,
        },
    }


# ── Teachers ──────────────────────────────────────────────────────────────────
#
# Teachers are Users tagged with `job_title="Teacher"`. SchoolClass.teacher_id,
# Subject.teacher_id, and Timetable.teacher_id already FK into `users.id`, so
# a separate table would duplicate identity/auth fields. Teacher-specific
# metadata (qualification, subjects, hire_date) lives in `User.preferences`
# JSON — that column is owned by the user's own profile today and is safe to
# namespace under a "teacher" key without colliding.

TEACHER_JOB_TITLE = "Teacher"
_TEACHER_PREF_KEY = "teacher"


def _teacher_dict(u: User) -> dict:
    prefs = (u.preferences or {}).get(_TEACHER_PREF_KEY, {}) if u.preferences else {}
    # preferences stores the logical first/last split the frontend wants,
    # since User.full_name is a single field on the model.
    first = prefs.get("first_name") or (u.full_name.split(" ", 1)[0] if u.full_name else "")
    last = prefs.get("last_name") or (u.full_name.split(" ", 1)[1] if u.full_name and " " in u.full_name else "")
    return {
        "id": u.id,
        "first_name": first,
        "last_name": last,
        "email": u.email,
        "phone": u.phone,
        "department": u.department,
        "qualification": prefs.get("qualification"),
        "subjects": prefs.get("subjects", []),
        "hire_date": prefs.get("hire_date"),
        "is_active": u.status == UserStatus.ACTIVE,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _teacher_query_base(org_id: str):
    return select(User).where(
        User.org_id == org_id,
        User.is_deleted == False,
        User.job_title == TEACHER_JOB_TITLE,
    )


@router.get("/teachers", dependencies=[_can_read])
async def list_teachers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = _teacher_query_base(current_user.org_id)
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(User.full_name.ilike(term), User.email.ilike(term))
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    result = await db.execute(
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return {
        "items": [_teacher_dict(u) for u in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/teachers/{id}", dependencies=[_can_read])
async def get_teacher(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        _teacher_query_base(current_user.org_id).where(User.id == id)
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher not found for id: {id}")
    return _teacher_dict(teacher)


@router.post("/teachers", status_code=201, dependencies=[_can_write])
async def create_teacher(
    data: TeacherCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    logger.info(
        "teacher_create.start org=%s actor=%s email=%s",
        org_id, current_user.id, data.email,
    )

    # Email is unique per org for teachers (and users in general). Check
    # before inserting so we can return a specific 409 instead of a
    # generic IntegrityError from a future UNIQUE index.
    existing = (await db.execute(
        select(User.id).where(
            User.email == data.email,
            User.org_id == org_id,
            User.is_deleted == False,
        )
    )).scalar_one_or_none()
    if existing:
        logger.warning(
            "teacher_create.duplicate_email org=%s email=%s",
            org_id, data.email,
        )
        raise HTTPException(
            status_code=409,
            detail=f"Teacher already exists with email: {data.email}",
        )

    full_name = f"{data.first_name} {data.last_name}".strip()
    prefs = {
        _TEACHER_PREF_KEY: {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "qualification": data.qualification,
            "subjects": data.subjects or [],
            "hire_date": data.hire_date.isoformat() if data.hire_date else None,
        }
    }
    teacher = User(
        email=data.email,
        full_name=full_name,
        phone=data.phone,
        department=data.department,
        job_title=TEACHER_JOB_TITLE,
        status=UserStatus.ACTIVE,
        org_id=org_id,
        preferences=prefs,
    )
    db.add(teacher)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        logger.warning(
            "teacher_create.integrity_error org=%s email=%s err=%s",
            org_id, data.email, e.orig,
        )
        raise HTTPException(
            status_code=409,
            detail="Teacher could not be created due to a database conflict.",
        )

    logger.info(
        "teacher_create.ok org=%s id=%s email=%s",
        org_id, teacher.id, teacher.email,
    )
    await log_action(
        db, AuditAction.RECORD_CREATED, org_id, actor=current_user,
        resource_type="Teacher", resource_id=teacher.id,
        resource_label=teacher.full_name or teacher.email,
        new_values={"email": teacher.email, "department": teacher.department},
        request=request,
    )
    return _teacher_dict(teacher)


@router.patch("/teachers/{id}", dependencies=[_can_write])
async def update_teacher(
    id: str,
    data: TeacherUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    org_id = current_user.org_id
    result = await db.execute(_teacher_query_base(org_id).where(User.id == id))
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher not found for id: {id}")

    updates = data.model_dump(exclude_unset=True)

    # Guard: changing email to another teacher's email in the same org
    # must return a specific 409, not a generic 500.
    if "email" in updates and updates["email"] and updates["email"] != teacher.email:
        clash = (await db.execute(
            select(User.id).where(
                User.email == updates["email"],
                User.org_id == org_id,
                User.is_deleted == False,
                User.id != id,
            )
        )).scalar_one_or_none()
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"Teacher already exists with email: {updates['email']}",
            )
        teacher.email = updates["email"]

    # Direct-mapped User columns.
    for col in ("phone", "department"):
        if col in updates:
            setattr(teacher, col, updates[col])

    # is_active maps onto UserStatus.
    if "is_active" in updates and updates["is_active"] is not None:
        teacher.status = UserStatus.ACTIVE if updates["is_active"] else UserStatus.INACTIVE

    # Pref-backed fields (and name split).
    prefs = dict(teacher.preferences or {})
    tpref = dict(prefs.get(_TEACHER_PREF_KEY, {}))
    if "first_name" in updates and updates["first_name"]:
        tpref["first_name"] = updates["first_name"]
    if "last_name" in updates and updates["last_name"]:
        tpref["last_name"] = updates["last_name"]
    if "qualification" in updates:
        tpref["qualification"] = updates["qualification"]
    if "subjects" in updates and updates["subjects"] is not None:
        tpref["subjects"] = updates["subjects"]
    if "hire_date" in updates:
        tpref["hire_date"] = updates["hire_date"].isoformat() if updates["hire_date"] else None

    if tpref.get("first_name") or tpref.get("last_name"):
        teacher.full_name = f"{tpref.get('first_name', '')} {tpref.get('last_name', '')}".strip()

    prefs[_TEACHER_PREF_KEY] = tpref
    teacher.preferences = prefs

    # SQLAlchemy doesn't always detect nested-dict mutation on JSON columns;
    # flag the attribute dirty so the UPDATE fires.
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(teacher, "preferences")

    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, org_id, actor=current_user,
        resource_type="Teacher", resource_id=teacher.id,
        resource_label=teacher.full_name or teacher.email,
        new_values=updates, request=request,
    )
    return _teacher_dict(teacher)


@router.delete("/teachers/{id}", status_code=204, dependencies=[_can_write])
async def delete_teacher(
    id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        _teacher_query_base(current_user.org_id).where(User.id == id)
    )
    teacher = result.scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail=f"Teacher not found for id: {id}")
    teacher.is_deleted = True
    from datetime import datetime, timezone
    teacher.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="Teacher", resource_id=teacher.id,
        resource_label=teacher.full_name or teacher.email,
        severity="warning", request=request,
    )


# ── Lesson Planner (Phase 6.4) ───────────────────────────────────────────────
#
# Teachers own their plans. Scoping rules:
#   - Admins / managers → see everything in the org.
#   - Teachers         → see their own plans, regardless of status.
#   - Students (read)  → see only PUBLISHED plans for their class.
#
# Ownership is enforced server-side from current_user.id. The frontend
# never sends "as teacher X" — we look the user up.


def _lesson_dict(lp: LessonPlan, subject_name: str | None = None, class_name: str | None = None, teacher_name: str | None = None) -> dict:
    return {
        "id": lp.id,
        "title": lp.title,
        "class_id": lp.class_id,
        "class_name": class_name,
        "subject_id": lp.subject_id,
        "subject_name": subject_name,
        "teacher_id": lp.teacher_id,
        "teacher_name": teacher_name,
        "lesson_date": lp.lesson_date.isoformat() if lp.lesson_date else None,
        "period": lp.period,
        "duration_minutes": lp.duration_minutes,
        "objectives": lp.objectives,
        "activities": lp.activities,
        "materials": lp.materials,
        "homework": lp.homework,
        "notes": lp.notes,
        "status": lp.status.value if hasattr(lp.status, "value") else lp.status,
        "created_at": lp.created_at.isoformat() if lp.created_at else None,
        "updated_at": lp.updated_at.isoformat() if lp.updated_at else None,
    }


def _is_admin_role(user: User) -> bool:
    return user.is_superadmin or any(
        r.slug in {"org_admin", "manager", "super_admin"} for r in user.roles
    )


@router.get("/lessons", dependencies=[_lessons_read])
async def list_lessons(
    class_id: str | None = None,
    subject_id: str | None = None,
    teacher_id: str | None = None,
    start_date: str | None = None,  # inclusive ISO date
    end_date: str | None = None,    # inclusive ISO date
    status: str | None = None,      # "draft" | "published"
    mine: bool = False,             # shortcut: filter to current teacher's plans
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Weekly view consumes this with start_date/end_date set to Mon..Sun.
    Non-admin teachers see their own plans unless an admin explicitly widens
    the query."""
    query = select(LessonPlan).where(
        LessonPlan.org_id == current_user.org_id,
        LessonPlan.is_deleted == False,
    )

    # Scoping: non-admins see only their own plans, regardless of filters.
    if not _is_admin_role(current_user):
        query = query.where(LessonPlan.teacher_id == current_user.id)
    elif mine:
        query = query.where(LessonPlan.teacher_id == current_user.id)
    elif teacher_id:
        query = query.where(LessonPlan.teacher_id == teacher_id)

    if class_id:
        query = query.where(LessonPlan.class_id == class_id)
    if subject_id:
        query = query.where(LessonPlan.subject_id == subject_id)
    if status in ("draft", "published"):
        query = query.where(LessonPlan.status == LessonPlanStatus(status))
    if start_date:
        try:
            query = query.where(LessonPlan.lesson_date >= date.fromisoformat(start_date))
        except ValueError:
            raise HTTPException(400, detail="Invalid start_date; expected YYYY-MM-DD")
    if end_date:
        try:
            query = query.where(LessonPlan.lesson_date <= date.fromisoformat(end_date))
        except ValueError:
            raise HTTPException(400, detail="Invalid end_date; expected YYYY-MM-DD")

    query = query.order_by(LessonPlan.lesson_date.asc(), LessonPlan.period.asc().nullslast())
    result = await db.execute(query)
    plans = result.scalars().all()

    # Hydrate names in a single batch lookup each — avoids N+1.
    subj_ids = {p.subject_id for p in plans if p.subject_id}
    class_ids = {p.class_id for p in plans if p.class_id}
    teacher_ids = {p.teacher_id for p in plans if p.teacher_id}
    subjects_by_id: dict[str, str] = {}
    classes_by_id: dict[str, str] = {}
    teachers_by_id: dict[str, str] = {}
    if subj_ids:
        for s in (await db.execute(select(Subject).where(Subject.id.in_(subj_ids)))).scalars().all():
            subjects_by_id[s.id] = s.name
    if class_ids:
        for c in (await db.execute(select(SchoolClass).where(SchoolClass.id.in_(class_ids)))).scalars().all():
            classes_by_id[c.id] = c.name
    if teacher_ids:
        for u in (await db.execute(select(User).where(User.id.in_(teacher_ids)))).scalars().all():
            teachers_by_id[u.id] = u.full_name

    return {
        "items": [
            _lesson_dict(
                p,
                subject_name=subjects_by_id.get(p.subject_id),
                class_name=classes_by_id.get(p.class_id),
                teacher_name=teachers_by_id.get(p.teacher_id) if p.teacher_id else None,
            )
            for p in plans
        ],
        "total": len(plans),
    }


@router.post("/lessons", status_code=201, dependencies=[_can_write])
async def create_lesson(
    payload: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    required = ("title", "class_id", "subject_id", "lesson_date")
    missing = [k for k in required if not (payload.get(k) or "").__str__().strip()]
    if missing:
        raise HTTPException(422, detail=f"Missing required fields: {', '.join(missing)}")
    try:
        lesson_date = date.fromisoformat(str(payload["lesson_date"]))
    except (TypeError, ValueError):
        raise HTTPException(422, detail="lesson_date must be YYYY-MM-DD")

    # teacher_id always snapped to the current user unless an admin explicitly
    # plans on behalf of someone else. Prevents a teacher from spoofing plans
    # for another teacher via a crafted payload.
    if _is_admin_role(current_user) and payload.get("teacher_id"):
        teacher_id = str(payload["teacher_id"])
    else:
        teacher_id = current_user.id

    # status either "draft" (default) or "published"
    raw_status = (payload.get("status") or "draft").lower()
    if raw_status not in ("draft", "published"):
        raise HTTPException(422, detail="status must be 'draft' or 'published'")

    plan = LessonPlan(
        title=str(payload["title"]).strip(),
        class_id=str(payload["class_id"]),
        subject_id=str(payload["subject_id"]),
        teacher_id=teacher_id,
        lesson_date=lesson_date,
        period=int(payload["period"]) if payload.get("period") not in (None, "") else None,
        duration_minutes=int(payload.get("duration_minutes") or 45),
        objectives=(payload.get("objectives") or None),
        activities=(payload.get("activities") or None),
        materials=(payload.get("materials") or None),
        homework=(payload.get("homework") or None),
        notes=(payload.get("notes") or None),
        status=LessonPlanStatus(raw_status),
        org_id=current_user.org_id,
    )
    db.add(plan)
    try:
        await db.flush()
    except IntegrityError as e:
        raise HTTPException(400, detail=f"Could not create lesson plan: {str(e.orig)}")
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="LessonPlan", resource_id=plan.id, resource_label=plan.title,
        new_values={"class_id": plan.class_id, "subject_id": plan.subject_id,
                    "status": plan.status.value if hasattr(plan.status, "value") else plan.status},
        request=request,
    )
    return _lesson_dict(plan)


async def _load_plan_or_404(db: AsyncSession, plan_id: str, user: User) -> LessonPlan:
    plan = (await db.execute(
        select(LessonPlan).where(
            LessonPlan.id == plan_id,
            LessonPlan.org_id == user.org_id,
            LessonPlan.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not plan:
        raise HTTPException(404, detail=f"Lesson plan not found: {plan_id}")
    # Non-admins can only act on their own plans.
    if not _is_admin_role(user) and plan.teacher_id != user.id:
        raise HTTPException(403, detail="You can only modify your own lesson plans")
    return plan


@router.patch("/lessons/{plan_id}", dependencies=[_can_write])
async def update_lesson(
    plan_id: str,
    payload: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await _load_plan_or_404(db, plan_id, current_user)

    editable = {
        "title", "class_id", "subject_id", "period", "duration_minutes",
        "objectives", "activities", "materials", "homework", "notes",
    }
    for key in editable:
        if key in payload:
            setattr(plan, key, payload[key] if payload[key] not in ("",) else None)

    if "lesson_date" in payload:
        try:
            plan.lesson_date = date.fromisoformat(str(payload["lesson_date"]))
        except (TypeError, ValueError):
            raise HTTPException(422, detail="lesson_date must be YYYY-MM-DD")

    if "status" in payload:
        raw = (payload.get("status") or "").lower()
        if raw not in ("draft", "published"):
            raise HTTPException(422, detail="status must be 'draft' or 'published'")
        plan.status = LessonPlanStatus(raw)

    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="LessonPlan", resource_id=plan.id, resource_label=plan.title,
        new_values=payload, request=request,
    )
    return _lesson_dict(plan)


@router.post("/lessons/{plan_id}/publish", dependencies=[_can_write])
async def publish_lesson(
    plan_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await _load_plan_or_404(db, plan_id, current_user)
    plan.status = LessonPlanStatus.PUBLISHED
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="LessonPlan", resource_id=plan.id, resource_label=plan.title,
        metadata={"action": "published"}, request=request,
    )
    return _lesson_dict(plan)


@router.delete("/lessons/{plan_id}", status_code=204, dependencies=[_can_write])
async def delete_lesson(
    plan_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = await _load_plan_or_404(db, plan_id, current_user)
    from datetime import datetime, timezone
    plan.is_deleted = True
    plan.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="LessonPlan", resource_id=plan.id, resource_label=plan.title,
        severity="warning", request=request,
    )
