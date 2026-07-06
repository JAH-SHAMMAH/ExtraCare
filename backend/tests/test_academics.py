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
from app.models.modules.school import Student, Subject
from app.models.modules.academics import Transcript, Recognition
from app.routers.modules.academics import (
    list_subject_selections, create_subject_selection, update_subject_selection, delete_subject_selection,
    list_transcripts, create_transcript, get_transcript, update_transcript,
    add_transcript_entry, delete_transcript_entry, delete_transcript,
    list_report_workflow, create_report_workflow, update_report_workflow, delete_report_workflow,
    list_recognitions, create_recognition, update_recognition, delete_recognition, recognition_leaderboard,
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

async def test_report_workflow_stage_transitions(db, org, teacher, school_class):
    r = await create_report_workflow(
        ReportApprovalCreate(class_id=school_class.id, term="Term 1"),
        request=None, db=db, current_user=teacher,
    )
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
        assert u.has_permission("school:subjects:write")
        assert u.has_permission("school:grades:write")
        assert u.has_permission("school:reports:write")
        assert u.has_permission("school:behaviour:write")
    # Students/parents: hold reports:read for their OWN card, but never the
    # admin academic tools (subjects/grades/reports:write/behaviour).
    for slug in ("student", "parent"):
        u = await _preset_user(db, org, slug)
        assert not u.has_permission("school:subjects:read")
        assert not u.has_permission("school:grades:read")
        assert not u.has_permission("school:reports:write")
        assert not u.has_permission("school:behaviour:read")
