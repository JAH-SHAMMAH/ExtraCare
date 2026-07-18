"""
School identity resolver
=========================
Helpers that map an authenticated User to their school-side identity for
`for_me=true` filtering. No dedicated student/teacher auth role exists yet
(see /me/school-context), so we resolve via:
  - Student: matching Student.email == User.email within the same org.
  - Teacher: User.id appearing as teacher_id on a class or subject.

These helpers return tuples of IDs that callers fold into their where-clauses.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.modules.school import Student, SchoolClass, Subject


def teacher_identity_filter():
    """SQLAlchemy condition selecting Users who are teachers, by the app's
    convention: their ``job_title`` contains "teacher" (case-insensitive). This
    matches the plain "Teacher" the create-teacher form assigns AND the
    subject-specific titles real teachers carry ("Physics Teacher", "ICT
    Teacher", …). Used by both the Teachers list and the dashboard counters so
    they always agree. Non-teaching staff (Accountant, Principal, …) are excluded.
    """
    return User.job_title.ilike("%teacher%")


async def resolve_linked_student_id(db: AsyncSession, user: User) -> str | None:
    if not user.email:
        return None
    result = await db.execute(
        select(Student.id).where(
            Student.email == user.email,
            Student.org_id == user.org_id,
            Student.is_deleted == False,
        )
    )
    return result.scalar_one_or_none()


async def resolve_taught_class_ids(db: AsyncSession, user: User) -> list[str]:
    result = await db.execute(
        select(SchoolClass.id).where(
            SchoolClass.teacher_id == user.id,
            SchoolClass.org_id == user.org_id,
        )
    )
    return [r for r in result.scalars().all()]


async def resolve_taught_subject_ids(db: AsyncSession, user: User) -> list[str]:
    result = await db.execute(
        select(Subject.id).where(
            Subject.teacher_id == user.id,
            Subject.org_id == user.org_id,
        )
    )
    return [r for r in result.scalars().all()]
