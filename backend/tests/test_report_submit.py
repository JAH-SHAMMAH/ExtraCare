"""The teacher half of the report workflow, which was stubbed and never wired.

`ReportApproval` has carried a `submitted_by` column and a `submitted` stage from
the start, and GET /report-workflow/mine filters on exactly that column — but
every write to the row was gated `school_admin:write`, so no teacher could ever
set it. That endpoint could only ever return an empty list to the people it was
written for. This adds the one transition that was missing: draft -> submitted.

Two decisions are pinned here, both about scope rather than mechanics:

  WHO. The row is unique on (class_id, term), so submitting speaks for the WHOLE
  class. Only the class's PC teacher may do it. A subject teacher pressing submit
  would be declaring every other subject finished on their colleagues' behalf —
  so they are refused, with a sentence that says their marks still count.

  HOW FAR. draft -> submitted and nothing else. Review, approval and publication
  stay `school_admin:write`. The ladder gets a rung; it does not get shorter.

Submitting deliberately does NOT make a report releasable — that is asserted
below, because it is the property that keeps this from becoming a way around the
approval the workflow exists to record.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.academics import ReportApproval
from app.models.modules.school import SchoolClass, Subject
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.academics import (
    list_my_report_workflow, submit_class_report,
)
from app.schemas.academics import (
    REPORT_PUBLISHABLE_STAGES, ReportSubmitRequest,
)

TERM = "Term 1"


async def _user(db, org, preset: str) -> User:
    role = Role(id=str(uuid.uuid4()), name=preset, slug=f"{preset}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[preset]), org_id=org.id,
                is_system=False)
    u = User(id=str(uuid.uuid4()), email=f"{preset}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=preset.title(), status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = [role]
    db.add_all([role, u])
    await db.commit()
    return u


async def _class(db, org, teacher: User | None = None) -> SchoolClass:
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary",
                      teacher_id=teacher.id if teacher else None, org_id=org.id)
    db.add(cls)
    await db.commit()
    return cls


async def _submit(db, user, cls, term=TERM, notes=None):
    return await submit_class_report(
        ReportSubmitRequest(class_id=cls.id, term=term, notes=notes),
        request=None, db=db, current_user=user,
    )


# ── the transition ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_class_teacher_can_submit_and_is_recorded(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)

    out = await _submit(db, teacher, cls)

    assert out.stage == "submitted"
    row = (await db.execute(select(ReportApproval))).scalars().one()
    assert row.submitted_by == teacher.id, "the whole point of the column"
    assert row.class_id == cls.id and row.term == TERM


@pytest.mark.asyncio
async def test_submitting_opens_the_workflow_row_if_none_exists(db, org):
    """A teacher should not have to ask an admin to create a row before they are
    allowed to fill it in — that was the shape of the original dead end."""
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    assert (await db.execute(select(ReportApproval))).scalars().first() is None

    await _submit(db, teacher, cls)

    assert (await db.execute(select(ReportApproval))).scalars().one().stage == "submitted"


@pytest.mark.asyncio
async def test_submitting_reuses_an_admin_opened_row_rather_than_duplicating(db, org):
    """uq_report_approval_class_term makes a second row impossible; it must be a
    sentence, not an IntegrityError."""
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term=TERM,
                          stage="draft", notes="opened by the office", org_id=org.id))
    await db.commit()

    await _submit(db, teacher, cls)

    rows = (await db.execute(select(ReportApproval))).scalars().all()
    assert len(rows) == 1 and rows[0].stage == "submitted"
    assert rows[0].notes == "opened by the office", "an unrelated field was clobbered"


@pytest.mark.asyncio
async def test_notes_are_attached_when_given(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    await _submit(db, teacher, cls, notes="Musa's Maths mark is pending a resit.")
    row = (await db.execute(select(ReportApproval))).scalars().one()
    assert "resit" in row.notes


# ── who may speak for the class ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_subject_teacher_who_is_not_the_class_teacher_is_refused(db, org):
    """The decision this feature turns on. One row covers the whole class, so a
    subject teacher pressing submit would declare every colleague's subject
    finished too."""
    class_teacher = await _user(db, org, "teacher")
    subject_teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, class_teacher)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics",
                   teacher_id=subject_teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await _submit(db, subject_teacher, cls)

    assert e.value.status_code == 403
    # The refusal must not read as "your marks don't count".
    assert "included" in e.value.detail.lower()
    assert (await db.execute(select(ReportApproval))).scalars().first() is None


@pytest.mark.asyncio
async def test_a_class_with_no_teacher_assigned_refuses_rather_than_letting_anyone_in(db, org):
    """_pc_teacher_id returns None here. An unassigned class is not an open one.

    The message matters as much as the refusal: telling a teacher "you are not the
    class teacher" when NOBODY is sends them looking for a colleague who does not
    exist. If Fairview's classes turn out to have no teacher_id set, this is the
    sentence that makes the feature's silence explicable instead of looking broken.
    """
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher=None)

    with pytest.raises(HTTPException) as e:
        await _submit(db, teacher, cls)
    assert e.value.status_code == 403
    assert "No class teacher is assigned" in e.value.detail
    assert "Only this class's teacher" not in e.value.detail


@pytest.mark.asyncio
async def test_the_grid_says_so_too_when_no_class_teacher_is_assigned(db, org):
    from app.routers.modules.platform import report_entry_grid

    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher=None)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()
    term = await _term(db, org)

    g = await report_entry_grid(class_id=cls.id, subject_id=subj.id, term_id=term.id,
                                db=db, current_user=teacher)
    assert g.submission.can_submit is False
    assert "No class teacher is assigned" in (g.submission.reason or "")


@pytest.mark.asyncio
async def test_an_admin_may_still_submit(db, org):
    """Admins already hold every other write on this row; the PC-teacher check is
    about who may speak for a class, and an admin already can."""
    admin = await _user(db, org, "org_admin")
    cls = await _class(db, org, teacher=None)

    out = await _submit(db, admin, cls)
    assert out.stage == "submitted"


@pytest.mark.asyncio
async def test_a_class_from_another_organisation_is_not_found(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    cls.org_id = str(uuid.uuid4())
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await _submit(db, teacher, cls)
    assert e.value.status_code == 404


# ── how far it goes ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submitting_twice_is_refused_and_says_where_it_got_to(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    await _submit(db, teacher, cls)

    with pytest.raises(HTTPException) as e:
        await _submit(db, teacher, cls)
    assert e.value.status_code == 409
    assert "submitted" in e.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["reviewed", "approved", "published"])
async def test_a_report_already_past_submission_cannot_be_pulled_back_by_a_teacher(db, org, stage):
    """Resubmitting an approved report would quietly undo the approval. Moving it
    back is an administrator's call."""
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    db.add(ReportApproval(id=str(uuid.uuid4()), class_id=cls.id, term=TERM,
                          stage=stage, org_id=org.id))
    await db.commit()

    with pytest.raises(HTTPException) as e:
        await _submit(db, teacher, cls)
    assert e.value.status_code == 409
    assert (await db.execute(select(ReportApproval))).scalars().one().stage == stage


@pytest.mark.asyncio
async def test_submitting_does_not_make_the_report_releasable(db, org):
    """The property that stops this becoming a way around approval: a teacher can
    hand the report in, and only an administrator can let it out."""
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)

    await _submit(db, teacher, cls)

    row = (await db.execute(select(ReportApproval))).scalars().one()
    assert row.stage not in REPORT_PUBLISHABLE_STAGES
    assert row.published_by is None and row.published_at is None
    assert row.approved_by is None and row.reviewed_by is None


@pytest.mark.asyncio
async def test_every_onward_stage_is_still_admin_only():
    """Asserted on the route table rather than by calling: these are FastAPI
    dependencies, which a direct function call bypasses. If the gate on PATCH is
    ever loosened, the teacher submit stops being one rung and becomes the ladder.
    """
    from app.routers.modules.academics import router

    patch_routes = [
        r for r in router.routes
        if getattr(r, "path", "").endswith("/report-workflow/{workflow_id}")
        and "PATCH" in getattr(r, "methods", set())
    ]
    assert patch_routes, "the stage-change route moved; this guard needs updating"
    perms = {
        getattr(d.dependency, "permission", None)
        for d in patch_routes[0].dependencies
    }
    assert "school_admin:write" in perms, perms


# ── the endpoint that was waiting for this ────────────────────────────────────

@pytest.mark.asyncio
async def test_report_workflow_mine_stops_being_permanently_empty(db, org):
    """Before this, `submitted_by` could never be set by a teacher, so their own
    submissions list was always empty."""
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)

    before = await list_my_report_workflow(page=1, page_size=25, db=db, current_user=teacher)
    assert before.total == 0

    await _submit(db, teacher, cls)

    after = await list_my_report_workflow(page=1, page_size=25, db=db, current_user=teacher)
    assert after.total == 1
    assert after.items[0].stage == "submitted"
    assert after.items[0].class_name == cls.name


@pytest.mark.asyncio
async def test_one_teachers_submission_does_not_appear_in_anothers_list(db, org):
    a = await _user(db, org, "teacher")
    b = await _user(db, org, "teacher")
    cls = await _class(db, org, a)

    await _submit(db, a, cls)

    assert (await list_my_report_workflow(page=1, page_size=25, db=db, current_user=b)).total == 0


# ── what the Make Report page is told ─────────────────────────────────────────

async def _grid(db, user, cls, subj, term):
    from app.routers.modules.platform import report_entry_grid
    return await report_entry_grid(class_id=cls.id, subject_id=subj.id,
                                   term_id=term.id, db=db, current_user=user)


async def _term(db, org, name=TERM):
    from app.models.modules.platform import AcademicTerm
    t = AcademicTerm(id=str(uuid.uuid4()), name=name, org_id=org.id)
    db.add(t)
    await db.commit()
    return t


@pytest.mark.asyncio
async def test_the_grid_offers_submit_to_the_class_teacher(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()
    term = await _term(db, org)

    g = await _grid(db, teacher, cls, subj, term)
    assert g.submission.can_submit is True
    assert g.submission.stage is None, "no workflow row exists yet"


@pytest.mark.asyncio
async def test_the_grid_explains_itself_to_a_subject_teacher_instead_of_going_quiet(db, org):
    """A hidden control with no explanation reads as a broken page. The refusal
    the endpoint would give is shown up front."""
    class_teacher = await _user(db, org, "teacher")
    subject_teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, class_teacher)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics",
                   teacher_id=subject_teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()
    term = await _term(db, org)

    g = await _grid(db, subject_teacher, cls, subj, term)
    assert g.submission.can_submit is False
    assert "included" in (g.submission.reason or "").lower()


@pytest.mark.asyncio
async def test_the_grid_reports_a_report_already_handed_in(db, org):
    teacher = await _user(db, org, "teacher")
    cls = await _class(db, org, teacher)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", teacher_id=teacher.id, org_id=org.id)
    db.add(subj)
    await db.commit()
    term = await _term(db, org)
    await _submit(db, teacher, cls)

    g = await _grid(db, teacher, cls, subj, term)
    assert g.submission.stage == "submitted" and g.submission.can_submit is False


@pytest.mark.asyncio
async def test_what_the_grid_offers_matches_what_the_endpoint_allows(db, org):
    """If these drift, the page shows a button that 403s. Asserted against the
    endpoint itself rather than a second copy of the rule.

    The subject is reassigned to each user in turn because the grid has its own,
    older gate — you must teach the subject in the class to load it at all — and
    this is about the submission rule sitting behind that, not the one in front.
    """
    class_teacher = await _user(db, org, "teacher")
    subject_teacher = await _user(db, org, "teacher")
    admin = await _user(db, org, "org_admin")
    cls = await _class(db, org, class_teacher)
    subj = Subject(id=str(uuid.uuid4()), name="Mathematics", org_id=org.id)
    db.add(subj)
    await db.commit()
    term = await _term(db, org)

    # class teacher: may submit. subject teacher: may not. admin: may.
    for user in (subject_teacher, class_teacher, admin):
        subj.teacher_id = user.id
        await db.commit()

        offered = (await _grid(db, user, cls, subj, term)).submission.can_submit
        try:
            await _submit(db, user, cls)
            allowed = True
        except HTTPException:
            allowed = False
        else:
            # Undo, so the next user faces the same starting state.
            await db.delete((await db.execute(select(ReportApproval))).scalars().one())
            await db.commit()

        assert offered == allowed, f"{user.full_name}: offered={offered} allowed={allowed}"
