"""
eClassroom Router
==================
Assignments, submissions and weekly reflections — the core teaching loop.

RBAC:
  - school:read   → list/view (students see their own, teachers see their class)
  - school:write  → create/grade/comment

Tenant isolation: every query pins org_id = current_user.org_id, never client.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_active_user
from app.models.user import User
from app.models.modules.school import (
    Assignment,
    AssignmentSubmission,
    SubmissionStatus,
    WeeklyReflection,
    Student,
)
from app.schemas.school_experience import (
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentResponse,
    SubmissionCreate,
    SubmissionGrade,
    SubmissionResponse,
    ReflectionCreate,
    ReflectionComment,
    ReflectionResponse,
)
from app.core.tenant import require_role_module
from app.core.permissions import PermissionChecker
from app.services.audit_service import log_action
from app.models.audit import AuditAction
from app.core.school_identity import (
    resolve_linked_student_id,
    resolve_taught_class_ids,
)

router = APIRouter(
    prefix="/classroom",
    tags=["eClassroom"],
    dependencies=[Depends(require_role_module("school"))],
)

_can_read = Depends(PermissionChecker("school:classroom:read"))
_can_write = Depends(PermissionChecker("school:classroom:write"))


# ── Assignments ───────────────────────────────────────────────────────────────


@router.get("/assignments", dependencies=[_can_read])
async def list_assignments(
    class_id: str | None = None,
    subject_id: str | None = None,
    teacher_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    for_me: bool = Query(default=False, description="Scope to the caller: student → own class; teacher → classes taught."),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(Assignment).where(
        Assignment.org_id == current_user.org_id,
        Assignment.is_deleted == False,
    )
    if class_id:
        query = query.where(Assignment.class_id == class_id)
    if subject_id:
        query = query.where(Assignment.subject_id == subject_id)
    if teacher_id:
        query = query.where(Assignment.teacher_id == teacher_id)
    if status_filter:
        query = query.where(Assignment.status == status_filter)
    if for_me:
        # Teachers see assignments they own; students see assignments for their class.
        # If we can't link the user to either, return an empty set rather than leaking
        # the whole school's queue.
        taught_classes = await resolve_taught_class_ids(db, current_user)
        if taught_classes:
            query = query.where(Assignment.class_id.in_(taught_classes))
        else:
            student_id = await resolve_linked_student_id(db, current_user)
            if student_id:
                student_class = (await db.execute(
                    select(Student.class_id).where(Student.id == student_id)
                )).scalar_one_or_none()
                if student_class:
                    query = query.where(Assignment.class_id == student_class)
                else:
                    query = query.where(Assignment.id == "__none__")
            else:
                query = query.where(Assignment.id == "__none__")

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar()
    query = query.order_by(Assignment.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [AssignmentResponse.model_validate(a).model_dump() for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/assignments", status_code=201, dependencies=[_can_write])
async def create_assignment(
    payload: AssignmentCreate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    assignment = Assignment(
        **payload.model_dump(),
        teacher_id=current_user.id,
        org_id=current_user.org_id,
    )
    db.add(assignment)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_CREATED, current_user.org_id, actor=current_user,
        resource_type="Assignment", resource_id=assignment.id,
        resource_label=getattr(assignment, "title", None) or assignment.id,
        request=request,
    )
    return AssignmentResponse.model_validate(assignment).model_dump()


@router.get("/assignments/{assignment_id}", dependencies=[_can_read])
async def get_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.org_id == current_user.org_id,
            Assignment.is_deleted == False,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return AssignmentResponse.model_validate(assignment).model_dump()


@router.patch("/assignments/{assignment_id}", dependencies=[_can_write])
async def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.org_id == current_user.org_id,
            Assignment.is_deleted == False,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(assignment, field, value)
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="Assignment", resource_id=assignment.id,
        resource_label=getattr(assignment, "title", None) or assignment.id,
        new_values=changes, request=request,
    )
    return AssignmentResponse.model_validate(assignment).model_dump()


@router.delete("/assignments/{assignment_id}", status_code=204, dependencies=[_can_write])
async def delete_assignment(
    assignment_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.org_id == current_user.org_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    assignment.is_deleted = True
    assignment.deleted_at = datetime.now(timezone.utc)
    await log_action(
        db, AuditAction.RECORD_DELETED, current_user.org_id, actor=current_user,
        resource_type="Assignment", resource_id=assignment.id,
        resource_label=getattr(assignment, "title", None) or assignment.id,
        severity="warning", request=request,
    )


# ── Submissions ───────────────────────────────────────────────────────────────


@router.get("/assignments/{assignment_id}/submissions", dependencies=[_can_read])
async def list_submissions(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.org_id == current_user.org_id,
        )
    )
    subs = result.scalars().all()
    return {"items": [SubmissionResponse.model_validate(s).model_dump() for s in subs]}


@router.post("/submissions", status_code=201, dependencies=[_can_write])
async def create_submission(
    payload: SubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify the assignment belongs to this tenant — prevents cross-tenant writes
    assignment = (await db.execute(
        select(Assignment).where(
            Assignment.id == payload.assignment_id,
            Assignment.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    submission = AssignmentSubmission(
        assignment_id=payload.assignment_id,
        student_id=payload.student_id,
        content=payload.content,
        file_url=payload.file_url,
        submitted_at=datetime.now(timezone.utc),
        status=SubmissionStatus.SUBMITTED,
        org_id=current_user.org_id,
    )
    db.add(submission)
    await db.flush()
    return SubmissionResponse.model_validate(submission).model_dump()


@router.patch("/submissions/{submission_id}/grade", dependencies=[_can_write])
async def grade_submission(
    submission_id: str,
    payload: SubmissionGrade,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.id == submission_id,
            AssignmentSubmission.org_id == current_user.org_id,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found.")

    sub.score = payload.score
    sub.feedback = payload.feedback
    sub.graded_by = current_user.id
    sub.graded_at = datetime.now(timezone.utc)
    sub.status = SubmissionStatus.GRADED
    await db.flush()
    await log_action(
        db, AuditAction.RECORD_UPDATED, current_user.org_id, actor=current_user,
        resource_type="AssignmentSubmission", resource_id=sub.id,
        resource_label=f"graded submission {sub.id}",
        severity="warning",
        metadata={"score": payload.score, "assignment_id": sub.assignment_id, "student_id": sub.student_id},
        request=request,
    )
    return SubmissionResponse.model_validate(sub).model_dump()


@router.get("/my-submissions", dependencies=[_can_read])
async def my_submissions(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Return a student's own submissions — used by the student CBT/classroom UI."""
    result = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == student_id,
            AssignmentSubmission.org_id == current_user.org_id,
        ).order_by(AssignmentSubmission.created_at.desc())
    )
    subs = result.scalars().all()
    return {"items": [SubmissionResponse.model_validate(s).model_dump() for s in subs]}


# ── Weekly Reflections ────────────────────────────────────────────────────────


@router.get("/reflections", dependencies=[_can_read])
async def list_reflections(
    student_id: str | None = None,
    for_me: bool = Query(default=False, description="Scope to the caller's linked student record."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = select(WeeklyReflection).where(WeeklyReflection.org_id == current_user.org_id)
    if student_id:
        query = query.where(WeeklyReflection.student_id == student_id)
    if for_me:
        linked = await resolve_linked_student_id(db, current_user)
        # No link → empty result rather than the whole school's reflections.
        query = query.where(WeeklyReflection.student_id == (linked or "__none__"))
    query = query.order_by(WeeklyReflection.week_start.desc())
    items = (await db.execute(query)).scalars().all()
    return {"items": [ReflectionResponse.model_validate(r).model_dump() for r in items]}


@router.post("/reflections", status_code=201, dependencies=[_can_write])
async def create_reflection(
    payload: ReflectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify student exists in this tenant
    student = (await db.execute(
        select(Student).where(
            Student.id == payload.student_id,
            Student.org_id == current_user.org_id,
        )
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    reflection = WeeklyReflection(
        **payload.model_dump(),
        org_id=current_user.org_id,
    )
    db.add(reflection)
    await db.flush()
    return ReflectionResponse.model_validate(reflection).model_dump()


@router.patch("/reflections/{reflection_id}/comment", dependencies=[_can_write])
async def comment_reflection(
    reflection_id: str,
    payload: ReflectionComment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(WeeklyReflection).where(
            WeeklyReflection.id == reflection_id,
            WeeklyReflection.org_id == current_user.org_id,
        )
    )
    reflection = result.scalar_one_or_none()
    if not reflection:
        raise HTTPException(status_code=404, detail="Reflection not found.")

    reflection.teacher_comment = payload.teacher_comment
    reflection.commented_by = current_user.id
    reflection.commented_at = datetime.now(timezone.utc)
    await db.flush()
    return ReflectionResponse.model_validate(reflection).model_dump()
