"""Tests for Admissions & Enrollment (Batch 2).

Covers the student lifecycle: applications (+ admit→Student), entrance exams
(+ results), promotions (class roll-over effects), transfers (roster effects),
tenant isolation, and the RBAC contract. Handlers are called directly per the
conftest convention.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student, SchoolClass
from app.models.modules.admissions import PromotionRecord
from app.models.audit import AuditLog
from app.routers.modules.admissions import (
    list_applications, create_application, update_application, delete_application, admit_application,
    create_entrance_exam, list_entrance_exams, add_exam_result, list_exam_results,
    update_exam_result, delete_exam_result,
    create_promotions, preview_promotions, revert_promotion_batch, list_promotions,
    create_transfer, list_transfers, update_transfer,
    create_pickup, list_pickups, update_pickup, delete_pickup,
    create_post_entrance, list_post_entrance, update_post_entrance,
)
from app.schemas.admissions import (
    AdmissionApplicationCreate, AdmissionApplicationUpdate, AdmitRequest,
    EntranceExamCreate, EntranceExamResultCreate,
    PromotionCreate, TransferCreate, TransferUpdate,
    AuthorizedPickupCreate, AuthorizedPickupUpdate,
    PostEntranceFormCreate, PostEntranceFormUpdate,
)


pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug: str) -> User:
    u = User(
        id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
        full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id,
    )
    role = Role(
        id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
        permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False,
    )
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _make_class(db, org, name="Grade 11A") -> SchoolClass:
    c = SchoolClass(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(c)
    await db.commit()
    return c


async def _make_student(db, org, cls, first="Kid", last="One", sid=None) -> Student:
    s = Student(
        id=str(uuid.uuid4()), student_id=sid or f"S-{uuid.uuid4().hex[:5]}",
        first_name=first, last_name=last, class_id=cls.id if cls else None,
        is_active=True, org_id=org.id,
    )
    db.add(s)
    await db.commit()
    return s


# ── Applications ──────────────────────────────────────────────────────────────

async def test_application_create_list_search(db, org, teacher, school_class):
    a = await create_application(
        AdmissionApplicationCreate(first_name="Ada", last_name="Lovelace",
                                   guardian_name="Byron", applying_for_class_id=school_class.id),
        request=None, db=db, current_user=teacher,
    )
    assert a.full_name == "Ada Lovelace"
    assert a.applying_for_class_name == school_class.name
    assert a.status == "enquiry"

    listing = await list_applications(status=None, search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1
    found = await list_applications(status=None, search="lovelace", page=1, page_size=25, db=db, current_user=teacher)
    assert found.total == 1
    by_status = await list_applications(status="applied", search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert by_status.total == 0


async def test_application_bad_status_rejected(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_application(AdmissionApplicationCreate(first_name="A", last_name="B", status="nope"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_application_update_and_delete(db, org, teacher):
    a = await create_application(AdmissionApplicationCreate(first_name="A", last_name="B"),
                                 request=None, db=db, current_user=teacher)
    updated = await update_application(a.id, AdmissionApplicationUpdate(status="offered"),
                                      request=None, db=db, current_user=teacher)
    assert updated.status == "offered"
    await delete_application(a.id, request=None, db=db, current_user=teacher)
    listing = await list_applications(status=None, search=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 0


async def test_enquiry_appointment_schedule_and_filter(db, org, teacher):
    from datetime import datetime, timezone
    a = await create_application(AdmissionApplicationCreate(first_name="Pros", last_name="Pect"),
                                 request=None, db=db, current_user=teacher)
    # Defaults to no appointment.
    assert a.appointment_status == "none"

    when = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    booked = await update_application(
        a.id,
        AdmissionApplicationUpdate(appointment_at=when, appointment_status="scheduled",
                                   appointment_notes="Campus tour"),
        request=None, db=db, current_user=teacher,
    )
    assert booked.appointment_status == "scheduled"
    assert booked.appointment_notes == "Campus tour"

    # The Enquiry Appointment view filters to scheduled ones.
    scheduled = await list_applications(status=None, appointment_status="scheduled", search=None,
                                        page=1, page_size=25, db=db, current_user=teacher)
    assert scheduled.total == 1 and scheduled.items[0].id == a.id

    # A bogus appointment_status is rejected (protects the NOT NULL column).
    with pytest.raises(HTTPException) as exc:
        await update_application(a.id, AdmissionApplicationUpdate(appointment_status="maybe"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_admit_creates_student(db, org, teacher, school_class):
    a = await create_application(
        AdmissionApplicationCreate(first_name="New", last_name="Pupil", applying_for_class_id=school_class.id),
        request=None, db=db, current_user=teacher,
    )
    result = await admit_application(a.id, payload=AdmitRequest(), request=None, db=db, current_user=teacher)
    assert result.status == "admitted"
    assert result.admitted_student_id is not None

    student = (await db.execute(select(Student).where(Student.id == result.admitted_student_id))).scalar_one()
    assert student.first_name == "New"
    assert student.class_id == school_class.id
    assert student.org_id == org.id
    assert student.is_active is True

    # Idempotency: a second admit is rejected.
    with pytest.raises(HTTPException) as exc:
        await admit_application(a.id, payload=AdmitRequest(), request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_application_tenant_scoped(db, org, teacher):
    await create_application(AdmissionApplicationCreate(first_name="Org1", last_name="App"),
                             request=None, db=db, current_user=teacher)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_applications(status=None, search=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── Entrance Exams ────────────────────────────────────────────────────────────

async def test_entrance_exam_and_results(db, org, teacher):
    exam = await create_entrance_exam(EntranceExamCreate(title="2026 Assessment", max_score=50),
                                      request=None, db=db, current_user=teacher)
    assert exam.result_count == 0

    r = await add_exam_result(exam.id, EntranceExamResultCreate(candidate_name="Tunde", score=40, outcome="pass"),
                              request=None, db=db, current_user=teacher)
    assert r.candidate_name == "Tunde"

    # score > max rejected
    with pytest.raises(HTTPException) as exc:
        await add_exam_result(exam.id, EntranceExamResultCreate(candidate_name="Over", score=99),
                              request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422

    results = await list_exam_results(exam.id, db=db, current_user=teacher)
    assert len(results) == 1

    listing = await list_entrance_exams(status=None, page=1, page_size=25, db=db, current_user=teacher)
    assert listing.items[0].result_count == 1

    await delete_exam_result(r.id, db=db, current_user=teacher)
    assert await list_exam_results(exam.id, db=db, current_user=teacher) == []


async def test_exam_result_requires_exam_in_org(db, org, teacher):
    with pytest.raises(HTTPException) as exc:
        await add_exam_result("missing", EntranceExamResultCreate(candidate_name="X"),
                              request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Promotions ────────────────────────────────────────────────────────────────

async def test_promote_moves_students_to_new_class(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 11B")
    s1 = await _make_student(db, org, school_class, "Ada", "One")
    s2 = await _make_student(db, org, school_class, "Bem", "Two")

    created = await create_promotions(
        PromotionCreate(student_ids=[s1.id, s2.id], to_class_id=target.id, academic_year="2025/2026"),
        request=None, db=db, current_user=teacher,
    )
    assert len(created) == 2
    assert {c.to_class_name for c in created} == {"Grade 11B"}

    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.class_id == target.id

    history = await list_promotions(student_id=s1.id, page=1, page_size=50, db=db, current_user=teacher)
    assert history.total == 1
    assert history.items[0].from_class_name == school_class.name


async def test_promote_requires_to_class_when_promoted(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    with pytest.raises(HTTPException) as exc:
        await create_promotions(PromotionCreate(student_ids=[s1.id], outcome="promoted"),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_graduate_deactivates_student(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    await create_promotions(PromotionCreate(student_ids=[s1.id], outcome="graduated"),
                            request=None, db=db, current_user=teacher)
    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.is_active is False
    assert refreshed.class_id is None


# ── Promotion safety: atomicity / idempotency / audit / preview / revert ──────

async def test_promotion_atomic_rejects_unknown_student_no_partial(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 12A")
    good = await _make_student(db, org, school_class, "Good", "Kid")
    # A bad id alongside a good one must reject the WHOLE run with nothing applied.
    with pytest.raises(HTTPException) as exc:
        await create_promotions(
            PromotionCreate(student_ids=[good.id, "does-not-exist"], to_class_id=target.id),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404
    # No records created, and the good student's class is untouched.
    count = (await db.execute(select(PromotionRecord).where(PromotionRecord.org_id == org.id))).scalars().all()
    assert count == []
    refreshed = (await db.execute(select(Student).where(Student.id == good.id))).scalar_one()
    assert refreshed.class_id == school_class.id


async def test_promotion_blocks_inactive_students(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 12B")
    s = await _make_student(db, org, school_class)
    # Graduate first → inactive.
    await create_promotions(PromotionCreate(student_ids=[s.id], outcome="graduated"),
                            request=None, db=db, current_user=teacher)
    # Re-processing an inactive student is refused (no double-apply).
    with pytest.raises(HTTPException) as exc:
        await create_promotions(PromotionCreate(student_ids=[s.id], to_class_id=target.id),
                                request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_promotion_preview_is_dry_run(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 12C")
    active = await _make_student(db, org, school_class, "Active", "One")
    gone = await _make_student(db, org, school_class, "Gone", "Two")
    await create_promotions(PromotionCreate(student_ids=[gone.id], outcome="graduated"),
                            request=None, db=db, current_user=teacher)

    before = (await db.execute(select(PromotionRecord).where(PromotionRecord.org_id == org.id))).scalars().all()
    preview = await preview_promotions(
        PromotionCreate(student_ids=[active.id, gone.id], to_class_id=target.id),
        db=db, current_user=teacher,
    )
    assert preview.eligible_count == 1
    assert preview.skipped_count == 1
    # Dry-run wrote nothing new.
    after = (await db.execute(select(PromotionRecord).where(PromotionRecord.org_id == org.id))).scalars().all()
    assert len(after) == len(before)


async def test_promotion_writes_before_after_audit(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 12D")
    s = await _make_student(db, org, school_class)
    await create_promotions(PromotionCreate(student_ids=[s.id], to_class_id=target.id),
                            request=None, db=db, current_user=teacher)
    logs = (await db.execute(
        select(AuditLog).where(AuditLog.org_id == org.id, AuditLog.resource_type == "Student")
    )).scalars().all()
    assert logs, "expected an audit row for the roster change"
    entry = next(l for l in logs if l.resource_id == s.id)
    assert entry.actor_id == teacher.id
    assert entry.old_values.get("class_id") == school_class.id
    assert entry.new_values.get("class_id") == target.id


async def test_promotion_revert_restores_state(db, org, teacher, school_class):
    target = await _make_class(db, org, "Grade 12E")
    s1 = await _make_student(db, org, school_class, "A", "One")
    s2 = await _make_student(db, org, school_class, "B", "Two")
    created = await create_promotions(
        PromotionCreate(student_ids=[s1.id, s2.id], to_class_id=target.id),
        request=None, db=db, current_user=teacher,
    )
    batch_id = created[0].batch_id
    assert all(c.batch_id == batch_id for c in created)
    # Students moved.
    assert (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one().class_id == target.id

    result = await revert_promotion_batch(batch_id, request=None, db=db, current_user=teacher)
    assert result.reverted == 2
    # Restored to original class.
    assert (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one().class_id == school_class.id
    # Second revert is a no-op (idempotent) → 404.
    with pytest.raises(HTTPException) as exc:
        await revert_promotion_batch(batch_id, request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_graduation_revert_reactivates(db, org, teacher, school_class):
    s = await _make_student(db, org, school_class)
    created = await create_promotions(PromotionCreate(student_ids=[s.id], outcome="graduated"),
                                      request=None, db=db, current_user=teacher)
    graduated = (await db.execute(select(Student).where(Student.id == s.id))).scalar_one()
    assert graduated.is_active is False
    await revert_promotion_batch(created[0].batch_id, request=None, db=db, current_user=teacher)
    restored = (await db.execute(select(Student).where(Student.id == s.id))).scalar_one()
    assert restored.is_active is True
    assert restored.class_id == school_class.id
    assert restored.graduation_date is None


# ── Transfers ─────────────────────────────────────────────────────────────────

async def test_transfer_create_and_complete_deactivates(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    t = await create_transfer(TransferCreate(student_id=s1.id, transfer_type="transfer_out", status="pending"),
                              request=None, db=db, current_user=teacher)
    assert t.status == "pending"
    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.is_active is True

    await update_transfer(t.id, TransferUpdate(status="completed"), request=None, db=db, current_user=teacher)
    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.is_active is False


async def test_transfer_completed_on_create_deactivates(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    await create_transfer(TransferCreate(student_id=s1.id, status="completed"),
                          request=None, db=db, current_user=teacher)
    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.is_active is False


async def test_transfer_blocks_already_inactive_student(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    await create_transfer(TransferCreate(student_id=s1.id, status="completed"),
                          request=None, db=db, current_user=teacher)
    # Second transfer for the now-departed student is refused (no double-process).
    with pytest.raises(HTTPException) as exc:
        await create_transfer(TransferCreate(student_id=s1.id, status="pending"),
                              request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_transfer_double_complete_is_idempotent(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    t = await create_transfer(TransferCreate(student_id=s1.id, status="pending"),
                              request=None, db=db, current_user=teacher)
    await update_transfer(t.id, TransferUpdate(status="completed"), request=None, db=db, current_user=teacher)
    # Re-completing an already-completed transfer must not error or re-apply.
    again = await update_transfer(t.id, TransferUpdate(status="completed"), request=None, db=db, current_user=teacher)
    assert again.status == "completed"
    refreshed = (await db.execute(select(Student).where(Student.id == s1.id))).scalar_one()
    assert refreshed.is_active is False


async def test_transfer_filter_and_tenant_scope(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class)
    await create_transfer(TransferCreate(student_id=s1.id, status="pending"),
                          request=None, db=db, current_user=teacher)
    pending = await list_transfers(status="pending", page=1, page_size=25, db=db, current_user=teacher)
    assert pending.total == 1

    # transfer_type filter (powers the Withdrawal List view). The record above
    # defaults to transfer_out, so a withdrawal filter yields nothing.
    withdrawals = await list_transfers(status=None, transfer_type="withdrawal", page=1, page_size=25, db=db, current_user=teacher)
    assert withdrawals.total == 0
    outs = await list_transfers(status=None, transfer_type="transfer_out", page=1, page_size=25, db=db, current_user=teacher)
    assert outs.total == 1

    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2t@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_transfers(status=None, page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── Authorized Pickups ─────────────────────────────────────────────────────────

async def test_pickup_create_list_and_student_filter(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class, first="Ada", sid="S-A")
    s2 = await _make_student(db, org, school_class, first="Bo", sid="S-B")
    p = await create_pickup(
        AuthorizedPickupCreate(student_id=s1.id, full_name="Grandma Ada",
                               relationship_type="guardian", phone="0800"),
        request=None, db=db, current_user=teacher,
    )
    assert p.is_active is True
    assert p.student_name == "Ada One"
    await create_pickup(AuthorizedPickupCreate(student_id=s2.id, full_name="Uncle Bo"),
                        request=None, db=db, current_user=teacher)

    everyone = await list_pickups(page=1, page_size=25, db=db, current_user=teacher)
    assert everyone.total == 2
    just_s1 = await list_pickups(student_id=s1.id, page=1, page_size=25, db=db, current_user=teacher)
    assert just_s1.total == 1 and just_s1.items[0].id == p.id


async def test_pickup_create_rejects_foreign_student(db, org, teacher, school_class):
    # A student from another org must not be pickup-registerable here.
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    await db.commit()
    foreign = await _make_student(db, other, None, sid="S-X")
    with pytest.raises(HTTPException) as exc:
        await create_pickup(AuthorizedPickupCreate(student_id=foreign.id, full_name="Intruder"),
                            request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_pickup_delete_is_deactivate_not_delete(db, org, teacher, school_class):
    s1 = await _make_student(db, org, school_class, sid="S-D")
    p = await create_pickup(AuthorizedPickupCreate(student_id=s1.id, full_name="Driver Dan"),
                            request=None, db=db, current_user=teacher)
    await delete_pickup(p.id, request=None, db=db, current_user=teacher)
    # Row survives; active_only hides it, unfiltered still shows it as inactive.
    active = await list_pickups(active_only=True, page=1, page_size=25, db=db, current_user=teacher)
    assert active.total == 0
    allrows = await list_pickups(page=1, page_size=25, db=db, current_user=teacher)
    assert allrows.total == 1 and allrows.items[0].is_active is False
    # Update can re-activate.
    reactivated = await update_pickup(p.id, AuthorizedPickupUpdate(is_active=True),
                                      request=None, db=db, current_user=teacher)
    assert reactivated.is_active is True


# ── Post Entrance Form ─────────────────────────────────────────────────────────

async def test_post_entrance_prefill_and_one_to_one(db, org, teacher, school_class):
    app = await create_application(
        AdmissionApplicationCreate(first_name="Zed", last_name="Kay",
                                   applying_for_class_id=school_class.id, gender="male"),
        request=None, db=db, current_user=teacher,
    )
    f = await create_post_entrance(
        PostEntranceFormCreate(application_id=app.id, father_name="Mr Kay"),
        request=None, db=db, current_user=teacher,
    )
    # Candidate identity prefilled from the linked application.
    assert f.full_name == "Zed Kay"
    assert f.applying_for_class_id == school_class.id
    assert f.applying_for_class_name == school_class.name
    assert f.candidate_name == "Zed Kay"
    assert f.father_name == "Mr Kay"
    assert f.status == "draft"
    # 1:1 — a second form for the same application is rejected.
    with pytest.raises(HTTPException) as exc:
        await create_post_entrance(PostEntranceFormCreate(application_id=app.id),
                                   request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 409


async def test_post_entrance_foreign_application_rejected(db, org, teacher, school_class):
    other = Organization(id=str(uuid.uuid4()), name="Other2", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    other_teacher = User(id=str(uuid.uuid4()), email=f"ot-{uuid.uuid4().hex[:6]}@e.com",
                         full_name="OT", status=UserStatus.ACTIVE, org_id=other.id)
    other_teacher.roles = []
    db.add(other_teacher)
    await db.commit()
    app = await create_application(AdmissionApplicationCreate(first_name="A", last_name="B"),
                                   request=None, db=db, current_user=other_teacher)
    # `teacher` (org) must not attach a form to another org's application.
    with pytest.raises(HTTPException) as exc:
        await create_post_entrance(PostEntranceFormCreate(application_id=app.id),
                                   request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


async def test_post_entrance_submit_stamps_and_list_filter(db, org, teacher, school_class):
    app = await create_application(AdmissionApplicationCreate(first_name="Su", last_name="Mit"),
                                   request=None, db=db, current_user=teacher)
    f = await create_post_entrance(PostEntranceFormCreate(application_id=app.id),
                                   request=None, db=db, current_user=teacher)
    assert f.submitted_at is None
    updated = await update_post_entrance(f.id, PostEntranceFormUpdate(status="submitted"),
                                         request=None, db=db, current_user=teacher)
    assert updated.status == "submitted" and updated.submitted_at is not None
    just = await list_post_entrance(application_id=app.id, page=1, page_size=25, db=db, current_user=teacher)
    assert just.total == 1 and just.items[0].id == f.id


# ── RBAC contract ─────────────────────────────────────────────────────────────

async def test_rbac_admissions_and_roster_scopes(db, org):
    for slug in ("org_admin", "manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:admissions:read")
        assert u.has_permission("school:admissions:write")
        assert u.has_permission("school:students:write")  # promotion/transfer
    staff = await _preset_user(db, org, "staff")
    assert staff.has_permission("school:admissions:read")
    assert not staff.has_permission("school:admissions:write")
    assert not staff.has_permission("school:students:write")
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:admissions:read")
        assert not u.has_permission("school:students:write")
