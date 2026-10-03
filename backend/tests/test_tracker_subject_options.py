"""The Performance Tracker's subject dropdown, built from the gate not beside it.

THE DEFECT. `performance_tracker` admits an administrator to any class and any
subject — `_report_admin` skips every teacher check in it. But the dropdown was
assembled in the client from `my-teaching-assignments`, i.e. the VIEWER's own
Timetable pairs, and an administrator teaches nothing. So their list came back
empty and the page said "You are not assigned to teach any subject in this
class": a report reachable by permission and unreachable by interface.

`result_analysis_classes` already states the principle for the CLASS dropdown —
build the list from the rule that enforces access, because a list assembled
alongside the gate is a list that disagrees with it. This applies the same rule
to subjects.

Driven as the real roles rather than one synthetic admin, because the whole
failure was role-dependent: the teacher path worked and the admin path did not,
and a test using only one of them would have missed it entirely.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.models.modules.platform import AcademicSession, AcademicTerm
from app.models.modules.school import SchoolClass, Student, Subject, Timetable
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import result_analysis_subjects

pytestmark = pytest.mark.asyncio


async def _user(db, org, preset: str, name: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{name}-{uuid.uuid4().hex[:6]}@x.com",
             full_name=name, status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


class W:
    pass


async def _world(db, org):
    """One class with THREE timetabled subjects, a class teacher who teaches only
    one of them, and an administrator who teaches none."""
    w = W()
    w.admin = await _user(db, org, "org_admin", "An Administrator")
    w.teacher = await _user(db, org, "teacher", "Ngozi Chukwu")
    w.other = await _user(db, org, "teacher", "Another Teacher")

    w.cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="JSS1",
                        teacher_id=w.teacher.id, org_id=org.id)
    w.maths = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    w.eng = Subject(id=str(uuid.uuid4()), name="English Language", org_id=org.id)
    w.bio = Subject(id=str(uuid.uuid4()), name="Biology", org_id=org.id)
    db.add_all([w.cls, w.maths, w.eng, w.bio])
    await db.commit()

    # Every subject is timetabled for the class; Ngozi teaches only Mathematics.
    for subj, who in ((w.maths, w.teacher), (w.eng, w.other), (w.bio, w.other)):
        db.add(Timetable(id=str(uuid.uuid4()), class_id=w.cls.id, subject_id=subj.id,
                         day_of_week=0, start_time="08:00", end_time="09:00",
                         teacher_id=who.id, org_id=org.id))
    await db.commit()
    return w


async def test_an_administrator_gets_the_classs_subjects_not_an_empty_list(db, org):
    """THE defect, directly. The administrator teaches nothing, and must still
    see every subject the class is timetabled for — those are exactly the ones
    the tracker can compute, since marks hang off (class, subject) pairs."""
    w = await _world(db, org)
    rows = await result_analysis_subjects(class_id=w.cls.id, db=db,
                                          current_user=w.admin)
    assert [r.subject_name for r in rows] == [
        "Biology", "English Language", "Mathematics"], "alphabetical, and all three"
    assert all(r.class_id == w.cls.id and r.class_name == "JSS1 A" for r in rows)


async def test_a_teacher_still_gets_only_what_they_teach(db, org):
    """The teacher path is unchanged — the fix must not widen anyone's view."""
    w = await _world(db, org)
    rows = await result_analysis_subjects(class_id=w.cls.id, db=db,
                                          current_user=w.teacher)
    assert [r.subject_name for r in rows] == ["Mathematics"]


async def test_the_list_matches_what_the_tracker_actually_accepts(db, org):
    """The point of deriving the list from the gate: every option offered must
    open, and an option the tracker would allow must not be missing.

    An option that 403s when clicked is worse than no option; an option missing
    that would have been allowed is a feature nobody can find.
    """
    from app.routers.modules.platform import performance_tracker

    w = await _world(db, org)
    db.add(AcademicSession(id=str(uuid.uuid4()), name="2025/2026", is_current=True,
                           org_id=org.id))
    db.add(AcademicTerm(id=str(uuid.uuid4()), name="Autumn", position=1, org_id=org.id))
    db.add(Student(id=str(uuid.uuid4()), student_id="FSN-0001", first_name="Ada",
                   last_name="Obi", class_id=w.cls.id, org_id=org.id))
    await db.commit()

    for who in (w.admin, w.teacher):
        offered = await result_analysis_subjects(class_id=w.cls.id, db=db,
                                                 current_user=who)
        for r in offered:
            # must not raise: everything offered is openable
            await performance_tracker(class_id=w.cls.id, subject_id=r.subject_id,
                                      db=db, current_user=who)

    # and the converse: a subject the teacher is NOT offered must be refused,
    # so the narrower list is the gate's doing and not a cosmetic filter.
    offered_ids = {r.subject_id for r in await result_analysis_subjects(
        class_id=w.cls.id, db=db, current_user=w.teacher)}
    assert w.bio.id not in offered_ids
    with pytest.raises(HTTPException) as e:
        await performance_tracker(class_id=w.cls.id, subject_id=w.bio.id,
                                  db=db, current_user=w.teacher)
    assert e.value.status_code == 403


async def test_a_class_with_no_timetable_offers_nothing_rather_than_erroring(db, org):
    """Early Years holds no subject rows by design (the Primary build removed
    them), so an admin opening one must get an empty list, not a 500."""
    w = await _world(db, org)
    bare = SchoolClass(id=str(uuid.uuid4()), name="Pre-Nursery Lilac",
                       level="Pre-Nursery", org_id=org.id)
    db.add(bare)
    await db.commit()
    rows = await result_analysis_subjects(class_id=bare.id, db=db,
                                          current_user=w.admin)
    assert rows == []


async def test_an_unknown_class_is_404(db, org):
    w = await _world(db, org)
    with pytest.raises(HTTPException) as e:
        await result_analysis_subjects(class_id=str(uuid.uuid4()), db=db,
                                       current_user=w.admin)
    assert e.value.status_code == 404


async def test_a_teacher_cannot_enumerate_another_classs_subjects(db, org):
    """The class gate applies before the subject list is built, so the dropdown
    cannot describe a class the tracker would refuse."""
    w = await _world(db, org)
    foreign = SchoolClass(id=str(uuid.uuid4()), name="SSS3 B", level="SSS3",
                          teacher_id=w.other.id, org_id=org.id)
    db.add(foreign)
    db.add(Timetable(id=str(uuid.uuid4()), class_id=foreign.id,
                     subject_id=w.maths.id, day_of_week=0, start_time="08:00",
                     end_time="09:00", teacher_id=w.other.id, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await result_analysis_subjects(class_id=foreign.id, db=db,
                                       current_user=w.teacher)
    assert e.value.status_code == 403
    # the admin may, which is the asymmetry the whole fix is about
    rows = await result_analysis_subjects(class_id=foreign.id, db=db,
                                          current_user=w.admin)
    assert [r.subject_name for r in rows] == ["Mathematics"]
