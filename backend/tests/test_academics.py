"""Tests for Academic Records & Recognition (Batch 3).

Subject selections, transcripts (+ averaging), report workflow, and the typed
Recognition model (conduct_point | academic_award) + house leaderboard. Plus
tenant isolation and the RBAC contract. Handlers called directly per convention.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import Student, Subject, SchoolClass, Timetable
from app.models.modules.academics import (
    Transcript, Recognition, ReportApproval
)
from app.models.modules.platform import (
    Assessment, AssessmentGroup, StudentAssessmentScore, AcademicTerm, AcademicSubTerm
)
from app.routers.modules.academics import (
    list_subject_selections, create_subject_selection, update_subject_selection, delete_subject_selection,
    list_transcripts, create_transcript, get_transcript, update_transcript,
    add_transcript_entry, delete_transcript_entry, delete_transcript,
    list_report_workflow, create_report_workflow, update_report_workflow, delete_report_workflow,
    list_recognitions, create_recognition, update_recognition, delete_recognition, recognition_leaderboard,
    list_grade_analysis,
)
from app.schemas.academics import (
    SubjectSelectionCreate, SubjectSelectionUpdate,
    TranscriptCreate, TranscriptEntryCreate, TranscriptUpdate,
    ReportApprovalCreate, ReportApprovalUpdate,
    RecognitionCreate, RecognitionUpdate,
)


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


async def _subject(db, org, name="Mathematics") -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


# ── Subject Selection ──────────────────────────────────────────────────────────

async def test_subject_selection_crud(db, org, teacher, student):
    subj = await _subject(db, org)
    sel = await create_subject_selection(
        SubjectSelectionCreate(student_id=student.id, subject_id=subj.id, academic_year="2025/2026"),
        request=None, db=db, current_user=teacher,
    )
    assert sel.subject_name == "Mathematics"
    assert sel.student_name == "Ada Okafor"

    listing = await list_subject_selections(student_id=None, subject_id=None, status=None,
                                            page=1, page_size=25, db=db, current_user=teacher)
    assert listing.total == 1

    updated = await update_subject_selection(sel.id, SubjectSelectionUpdate(status="approved"),
                                             db=db, current_user=teacher)
    assert updated.status == "approved"
    await delete_subject_selection(sel.id, db=db, current_user=teacher)
    assert (await list_subject_selections(student_id=None, subject_id=None, status=None,
                                          page=1, page_size=25, db=db, current_user=teacher)).total == 0


async def test_subject_selection_duplicate_409(db, org, teacher, student):
    # The 409 path rolls back, so keep it the LAST action on this session (the
    # production get_db wrapper isolates this per-request).
    subj = await _subject(db, org)
    await create_subject_selection(
        SubjectSelectionCreate(student_id=student.id, subject_id=subj.id, academic_year="2025/2026"),
        request=None, db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await create_subject_selection(
            SubjectSelectionCreate(student_id=student.id, subject_id=subj.id, academic_year="2025/2026"),
            request=None, db=db, current_user=teacher,
        )
    assert exc.value.status_code == 409


async def test_subject_selection_validates_refs(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await create_subject_selection(SubjectSelectionCreate(student_id=student.id, subject_id="nope"),
                                       request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 404


# ── Transcripts ────────────────────────────────────────────────────────────────

async def test_transcript_averaging_and_entries(db, org, teacher, student):
    t = await create_transcript(
        TranscriptCreate(student_id=student.id, term="Term 1", entries=[
            TranscriptEntryCreate(subject_name="Maths", score=80),
            TranscriptEntryCreate(subject_name="English", score=60),
        ]),
        request=None, db=db, current_user=teacher,
    )
    assert t.average == 70.0
    assert len(t.entries) == 2

    # Adding an entry recomputes the average.
    t2 = await add_transcript_entry(t.id, TranscriptEntryCreate(subject_name="Science", score=90),
                                    db=db, current_user=teacher)
    assert t2.average == pytest.approx(76.67, abs=0.01)

    # Removing one recomputes again.
    sci = next(e for e in t2.entries if e.subject_name == "Science")
    t3 = await delete_transcript_entry(t.id, sci.id, db=db, current_user=teacher)
    assert t3.average == 70.0

    issued = await update_transcript(t.id, TranscriptUpdate(status="issued"), db=db, current_user=teacher)
    assert issued.status == "issued"

    await delete_transcript(t.id, db=db, current_user=teacher)
    assert (await list_transcripts(student_id=None, page=1, page_size=25, db=db, current_user=teacher)).total == 0


async def test_transcript_get_detail(db, org, teacher, student):
    t = await create_transcript(TranscriptCreate(student_id=student.id, entries=[]),
                                request=None, db=db, current_user=teacher)
    detail = await get_transcript(t.id, db=db, current_user=teacher)
    assert detail.id == t.id
    assert detail.average is None


# ── Report Workflow ────────────────────────────────────────────────────────────

async def _workflow(db, teacher, school_class, term="Term 1"):
    return await create_report_workflow(
        ReportApprovalCreate(class_id=school_class.id, term=term),
        request=None, db=db, current_user=teacher,
    )


async def test_report_workflow_stage_transitions(db, org, teacher, school_class):
    r = await _workflow(db, teacher, school_class)
    assert r.stage == "draft"
    assert r.class_name == school_class.name

    advanced = await update_report_workflow(r.id, ReportApprovalUpdate(stage="submitted"),
                                            request=None, db=db, current_user=teacher)
    assert advanced.stage == "submitted"

    with pytest.raises(HTTPException) as exc:
        await update_report_workflow(r.id, ReportApprovalUpdate(stage="bogus"),
                                     request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422

    await delete_report_workflow(r.id, db=db, current_user=teacher)
    assert (await list_report_workflow(stage=None, page=1, page_size=25, db=db, current_user=teacher)).total == 0


async def test_report_workflow_walks_the_full_ladder(db, org, teacher, school_class):
    """One step at a time, all the way up, stamping an actor at each stage."""
    r = await _workflow(db, teacher, school_class)
    for stage in ("submitted", "reviewed", "approved", "published"):
        out = await update_report_workflow(r.id, ReportApprovalUpdate(stage=stage),
                                           request=None, db=db, current_user=teacher)
        assert out.stage == stage

    row = (await db.execute(select(ReportApproval).where(ReportApproval.id == r.id))).scalar_one()
    assert row.submitted_by == teacher.id
    assert row.reviewed_by == teacher.id
    assert row.approved_by == teacher.id
    # Releasing to parents carries its own stamp, not a shared "approved_by".
    assert row.published_by == teacher.id
    assert row.published_at is not None


async def test_report_workflow_rejects_stage_skips(db, org, teacher, school_class):
    """A jump straight to `published` would skip the review the row exists to
    record — every forward jump of more than one step is refused."""
    r = await _workflow(db, teacher, school_class)

    for target in ("reviewed", "approved", "published"):
        with pytest.raises(HTTPException) as exc:
            await update_report_workflow(r.id, ReportApprovalUpdate(stage=target),
                                         request=None, db=db, current_user=teacher)
        assert exc.value.status_code == 422
        assert "one stage at a time" in exc.value.detail

    row = (await db.execute(select(ReportApproval).where(ReportApproval.id == r.id))).scalar_one()
    assert row.stage == "draft"          # nothing moved
    assert row.published_at is None      # and nothing was stamped on the way


async def test_report_workflow_allows_backward_moves(db, org, teacher, school_class):
    """Rejection is a single move backwards of any distance: a reviewer sends an
    approved report straight back to draft without walking down the ladder."""
    r = await _workflow(db, teacher, school_class)
    for stage in ("submitted", "reviewed", "approved"):
        await update_report_workflow(r.id, ReportApprovalUpdate(stage=stage),
                                     request=None, db=db, current_user=teacher)

    out = await update_report_workflow(r.id, ReportApprovalUpdate(stage="draft"),
                                       request=None, db=db, current_user=teacher)
    assert out.stage == "draft"

    # Re-setting the same stage is a no-op, not a 422 — a PATCH must stay idempotent.
    same = await update_report_workflow(r.id, ReportApprovalUpdate(stage="draft"),
                                        request=None, db=db, current_user=teacher)
    assert same.stage == "draft"

    # And a published report can be pulled back the same way.
    for stage in ("submitted", "reviewed", "approved", "published"):
        await update_report_workflow(r.id, ReportApprovalUpdate(stage=stage),
                                     request=None, db=db, current_user=teacher)
    pulled = await update_report_workflow(r.id, ReportApprovalUpdate(stage="reviewed"),
                                          request=None, db=db, current_user=teacher)
    assert pulled.stage == "reviewed"
    row = (await db.execute(select(ReportApproval).where(ReportApproval.id == r.id))).scalar_one()
    # published_at survives the retraction: it records the last release, and the
    # gates read `stage`, never the timestamp.
    assert row.published_at is not None


async def test_report_workflow_create_refuses_a_duplicate(db, org, teacher, school_class):
    """One row per class + term. The second attempt gets a sentence naming the
    existing stage, not the constraint's 500."""
    await _workflow(db, teacher, school_class, term="Term 1")

    with pytest.raises(HTTPException) as exc:
        await _workflow(db, teacher, school_class, term="Term 1")
    assert exc.value.status_code == 409
    assert "already exists" in exc.value.detail

    # A different term is fine — the constraint is per (class, term).
    other = await _workflow(db, teacher, school_class, term="Term 2")
    assert other.stage == "draft"


async def test_report_workflow_notes_edit_needs_no_stage(db, org, teacher, school_class):
    """A PATCH that doesn't touch `stage` isn't subject to the ladder at all."""
    r = await _workflow(db, teacher, school_class)
    out = await update_report_workflow(r.id, ReportApprovalUpdate(notes="Waiting on Maths."),
                                       request=None, db=db, current_user=teacher)
    assert out.notes == "Waiting on Maths." and out.stage == "draft"


# ── Grade Analysis (Teacher Performance Report) ────────────────────────────────

async def test_grade_analysis_multi_class_same_subject(db, org, teacher):
    """Verify teacher seeing same subject in multiple classes is correctly scoped.

    CRITICAL TEST: Ensures Timetable scoping prevents a teacher from seeing
    StudentAssessmentScore from classes/subjects they don't teach.
    """
    # Setup: Create two classes (different class_ids, same teacher)
    class_a = SchoolClass(
        id=str(uuid.uuid4()), name="Year 9A", level="Secondary",
        academic_year="2025/2026", teacher_id=teacher.id, org_id=org.id
    )
    class_b = SchoolClass(
        id=str(uuid.uuid4()), name="Year 9B", level="Secondary",
        academic_year="2025/2026", teacher_id=teacher.id, org_id=org.id
    )
    db.add(class_a)
    db.add(class_b)

    # Create a subject
    subject = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    db.add(subject)

    # Create students: one in each class
    student_a = Student(
        id=str(uuid.uuid4()), student_id="A-001", first_name="Alice", last_name="Ahmed",
        class_id=class_a.id, org_id=org.id
    )
    student_b = Student(
        id=str(uuid.uuid4()), student_id="B-001", first_name="Bob", last_name="Brown",
        class_id=class_b.id, org_id=org.id
    )
    db.add(student_a)
    db.add(student_b)

    # Create Timetable entries: teacher teaches Math to both classes (Monday 08:00-09:00)
    tt_a = Timetable(
        id=str(uuid.uuid4()), class_id=class_a.id, subject_id=subject.id,
        day_of_week=0, start_time="08:00", end_time="09:00",
        teacher_id=teacher.id, org_id=org.id
    )
    tt_b = Timetable(
        id=str(uuid.uuid4()), class_id=class_b.id, subject_id=subject.id,
        day_of_week=0, start_time="09:00", end_time="10:00",
        teacher_id=teacher.id, org_id=org.id
    )
    db.add(tt_a)
    db.add(tt_b)

    # Create academic term
    term = AcademicTerm(
        id=str(uuid.uuid4()), name="Term 1", org_id=org.id
    )
    db.add(term)

    # Create academic sub-term (required by Assessment)
    sub_term = AcademicSubTerm(
        id=str(uuid.uuid4()), name="Full-Term", org_id=org.id
    )
    db.add(sub_term)

    # Create assessment group
    group = AssessmentGroup(
        id=str(uuid.uuid4()), name="Quiz 1", org_id=org.id
    )
    db.add(group)

    # Create assessments
    assessment_a = Assessment(
        id=str(uuid.uuid4()), name="Quiz 1A", group_id=group.id,
        term_id=term.id, sub_term_id=sub_term.id, max_score=20.0, org_id=org.id
    )
    assessment_b = Assessment(
        id=str(uuid.uuid4()), name="Quiz 1B", group_id=group.id,
        term_id=term.id, sub_term_id=sub_term.id, max_score=20.0, org_id=org.id
    )
    db.add(assessment_a)
    db.add(assessment_b)

    await db.flush()

    # Create StudentAssessmentScore: class A student scores 18/20, class B student scores 15/20
    score_a = StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=student_a.id, subject_id=subject.id,
        assessment_id=assessment_a.id, score=18.0, org_id=org.id
    )
    score_b = StudentAssessmentScore(
        id=str(uuid.uuid4()), student_id=student_b.id, subject_id=subject.id,
        assessment_id=assessment_b.id, score=15.0, org_id=org.id
    )
    db.add(score_a)
    db.add(score_b)
    await db.commit()

    # TEST 1: List all grades for this teacher (no filters)
    result = await list_grade_analysis(
        class_id=None, subject_id=None, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result["total"] == 2, "Should see both classes' aggregated scores"
    items = result["items"]
    assert len(items) == 2

    # Extract by student name to verify scoping
    alice_item = next((i for i in items if "Alice" in i["student_name"]), None)
    bob_item = next((i for i in items if "Bob" in i["student_name"]), None)
    assert alice_item is not None, "Should see Alice (class A student)"
    assert bob_item is not None, "Should see Bob (class B student)"

    # Verify Alice's data is from class A
    assert alice_item["total_score"] == 18.0
    assert alice_item["total_max_score"] == 20.0
    assert alice_item["percentage"] == 90.0
    assert alice_item["assessment_count"] == 1

    # Verify Bob's data is from class B
    assert bob_item["total_score"] == 15.0
    assert bob_item["total_max_score"] == 20.0
    assert bob_item["percentage"] == 75.0
    assert bob_item["assessment_count"] == 1

    # TEST 2: Filter by class_id (class A only)
    result_class_a = await list_grade_analysis(
        class_id=class_a.id, subject_id=None, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result_class_a["total"] == 1, "Should see only class A student"
    assert "Alice" in result_class_a["items"][0]["student_name"]

    # TEST 3: Filter by class_id (class B only)
    result_class_b = await list_grade_analysis(
        class_id=class_b.id, subject_id=None, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result_class_b["total"] == 1, "Should see only class B student"
    assert "Bob" in result_class_b["items"][0]["student_name"]

    # TEST 4: Filter by subject_id
    result_subject = await list_grade_analysis(
        class_id=None, subject_id=subject.id, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result_subject["total"] == 2, "Should see both students for this subject"

    # TEST 5: Filter by term_id
    result_term = await list_grade_analysis(
        class_id=None, subject_id=None, term_id=term.id,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result_term["total"] == 2, "Should see both students in this term"

    # TEST 6: Filter by class + subject combo
    result_combo = await list_grade_analysis(
        class_id=class_a.id, subject_id=subject.id, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher
    )
    assert result_combo["total"] == 1, "Should see only class A + math"
    assert "Alice" in result_combo["items"][0]["student_name"]


async def test_grade_analysis_teacher_without_classes(db, org):
    """Teacher with no Timetable assignments should see empty results."""
    teacher_no_class = User(
        id=str(uuid.uuid4()), email="lonely@example.com", full_name="Lonely Teacher",
        status=UserStatus.ACTIVE, org_id=org.id
    )
    teacher_no_class.roles = []
    db.add(teacher_no_class)
    await db.commit()

    result = await list_grade_analysis(
        class_id=None, subject_id=None, term_id=None,
        page=1, page_size=25, db=db, current_user=teacher_no_class
    )
    assert result["total"] == 0, "Teacher with no classes should see empty results"
    assert result["items"] == []


# ── Merit & Awards (Recognition) ────────────────────────────────────────────────

async def test_conduct_point_requires_points(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await create_recognition(RecognitionCreate(type="conduct_point", student_id=student.id),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


async def test_recognition_types_and_leaderboard(db, org, teacher, student):
    # conduct points across houses
    await create_recognition(RecognitionCreate(type="conduct_point", student_id=student.id,
                                               points=5, house="Red", category="helpfulness", term="Term 1"),
                             request=None, db=db, current_user=teacher)
    await create_recognition(RecognitionCreate(type="conduct_point", student_id=student.id,
                                               points=-2, house="Red", category="lateness", term="Term 1"),
                             request=None, db=db, current_user=teacher)
    await create_recognition(RecognitionCreate(type="conduct_point", student_id=student.id,
                                               points=4, house="Blue", term="Term 1"),
                             request=None, db=db, current_user=teacher)
    # an academic award (no points)
    award = await create_recognition(RecognitionCreate(type="academic_award", student_id=student.id,
                                                       title="Honor Roll", award_type="honor_roll", term="Term 1"),
                                     request=None, db=db, current_user=teacher)
    assert award.type == "academic_award"

    # filter by type
    conduct = await list_recognitions(type="conduct_point", student_id=None, house=None, term=None,
                                      page=1, page_size=25, db=db, current_user=teacher)
    assert conduct.total == 3
    awards = await list_recognitions(type="academic_award", student_id=None, house=None, term=None,
                                     page=1, page_size=25, db=db, current_user=teacher)
    assert awards.total == 1

    board = await recognition_leaderboard(term=None, db=db, current_user=teacher)
    totals = {h.house: h.total_points for h in board.houses}
    assert totals["Red"] == 3   # 5 - 2
    assert totals["Blue"] == 4
    # Red leads-or-equal ordering: highest first
    assert board.houses[0].total_points >= board.houses[-1].total_points


async def test_recognition_bad_award_type(db, org, teacher, student):
    with pytest.raises(HTTPException) as exc:
        await create_recognition(RecognitionCreate(type="academic_award", student_id=student.id,
                                                   award_type="trophy"),
                                 request=None, db=db, current_user=teacher)
    assert exc.value.status_code == 422


# ── Tenant isolation ──────────────────────────────────────────────────────────

async def test_academics_tenant_scoped(db, org, teacher, student):
    await create_recognition(RecognitionCreate(type="academic_award", student_id=student.id, title="Prize"),
                             request=None, db=db, current_user=teacher)
    other = Organization(id=str(uuid.uuid4()), name="Other", slug=f"o-{uuid.uuid4().hex[:6]}",
                         industry=IndustryType.SCHOOL, modules_enabled=["school"])
    db.add(other)
    teacher2 = User(id=str(uuid.uuid4()), email="t2a@example.com", full_name="T2",
                    status=UserStatus.ACTIVE, org_id=other.id)
    db.add(teacher2)
    await db.commit()
    theirs = await list_recognitions(type=None, student_id=None, house=None, term=None,
                                     page=1, page_size=25, db=db, current_user=teacher2)
    assert theirs.total == 0


# ── RBAC contract ─────────────────────────────────────────────────────────────

async def test_rbac_academics_scopes(db, org):
    for slug in ("org_admin", "manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:grades:write")
        assert u.has_permission("school:reports:write")
        assert u.has_permission("school:behaviour:write")
        assert u.has_permission("school:subjects:read")
    # Subject CRUD is academic TAXONOMY — admin-side. A teacher teaches subjects
    # and reads them for its pickers, but does not create/rename/delete them
    # (see the classroom preset in models/role.py).
    for slug in ("org_admin", "manager"):
        assert (await _preset_user(db, org, slug)).has_permission("school:subjects:write")
    assert not (await _preset_user(db, org, "teacher")).has_permission("school:subjects:write")
    # Students/parents: hold reports:read for their OWN card, but never the
    # admin academic tools (subjects/grades/reports:write/behaviour).
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:subjects:read")
        assert not u.has_permission("school:grades:read")
        assert not u.has_permission("school:reports:write")
        assert not u.has_permission("school:behaviour:read")
