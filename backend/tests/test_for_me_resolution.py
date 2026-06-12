"""
Tests for `for_me` identity resolution — the backbone of every personalised
list endpoint. Fail here and students see the whole school's data, or teachers
see nothing at all.
"""

from app.core.school_identity import (
    resolve_linked_student_id,
    resolve_taught_class_ids,
    resolve_taught_subject_ids,
)
from app.models.modules.school import Subject


async def test_student_resolves_via_shared_email(db, student_user, student):
    linked = await resolve_linked_student_id(db, student_user)
    assert linked == student.id


async def test_teacher_resolves_taught_classes(db, teacher, school_class):
    classes = await resolve_taught_class_ids(db, teacher)
    assert classes == [school_class.id]


async def test_teacher_resolves_taught_subjects(db, org, teacher):
    subj = Subject(name="Mathematics", teacher_id=teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()
    assert await resolve_taught_subject_ids(db, teacher) == [subj.id]


async def test_unlinked_user_gets_nothing(db, unlinked_user):
    assert await resolve_linked_student_id(db, unlinked_user) is None
    assert await resolve_taught_class_ids(db, unlinked_user) == []
    assert await resolve_taught_subject_ids(db, unlinked_user) == []


async def test_student_match_is_tenant_scoped(db, org, student):
    """A user in a different org must not resolve to this tenant's student."""
    from app.models.user import User, UserStatus
    from app.models.organization import Organization, IndustryType
    import uuid

    other_org = Organization(
        id=str(uuid.uuid4()),
        name="Rival School",
        slug=f"rival-{uuid.uuid4().hex[:6]}",
        industry=IndustryType.SCHOOL,
    )
    db.add(other_org)
    await db.commit()

    impostor = User(
        id=str(uuid.uuid4()),
        email=student.email,  # same email, different org
        full_name="Impostor",
        status=UserStatus.ACTIVE,
        org_id=other_org.id,
    )
    db.add(impostor)
    await db.commit()

    assert await resolve_linked_student_id(db, impostor) is None


async def test_soft_deleted_student_does_not_resolve(db, student_user, student):
    student.is_deleted = True
    await db.commit()
    assert await resolve_linked_student_id(db, student_user) is None


async def test_user_without_email_is_unlinked(db, org):
    """SSO-only edge case: guard must short-circuit before the DB lookup."""
    from app.models.user import User, UserStatus

    # Unpersisted — the helper should bail before touching the session.
    u = User(email=None, full_name="No-Email", status=UserStatus.ACTIVE, org_id=org.id)
    assert await resolve_linked_student_id(db, u) is None
