"""Custom comment slots: who may write one, and how a row is identified.

`report_comment_types` has defined named comment slots since S-1a, and nothing
could hold a value for one — `student_report_comments.kind` was head | pc and
only those two had entry or a place on the card. Every other slot an admin
created was inert.

Two things are pinned here:

  OWNERSHIP is the two rules that already existed, not a third. A slot is
  PC-teacher-writable by default (like `pc`) or admin-only when flagged (like
  `head`).

  IDENTITY is the slot, never `kind`. Every custom row carries the literal
  'custom', so `kind` cannot tell two slots apart — a query that filtered on it
  would match every slot at once, and a uniqueness key built on the slot's NAME
  would drift the moment someone renamed it, which is the defect migrations 131
  and 132 removed from two other tables.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.modules.platform import (
    AcademicSubTerm, AcademicTerm, ReportCommentType, StudentReportComment,
)
from app.models.modules.school import SchoolClass, Student
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.user import User, UserStatus
from app.routers.modules.platform import report_comment_grid, save_report_comments
from app.schemas.platform import CommentGridSave, CommentItem


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


async def _world(db, org):
    """A class whose PC teacher is the class teacher (the resolver's fallback)."""
    teacher = await _user(db, org, "teacher")
    cls = SchoolClass(id=str(uuid.uuid4()), name="JSS1 A", level="Secondary",
                      teacher_id=teacher.id, org_id=org.id)
    term = AcademicTerm(id=str(uuid.uuid4()), name="Autumn", org_id=org.id)
    sub = AcademicSubTerm(id=str(uuid.uuid4()), name="Full-Term", org_id=org.id)
    db.add_all([cls, term, sub])
    await db.commit()
    pupil = Student(id=str(uuid.uuid4()), student_id="S-1", first_name="Ada",
                    last_name="Obi", class_id=cls.id, org_id=org.id)
    db.add(pupil)
    await db.commit()
    return dict(teacher=teacher, cls=cls, term=term, sub=sub, pupil=pupil)


async def _slot(db, org, name: str, *, admin_only: bool, active: bool = True):
    s = ReportCommentType(id=str(uuid.uuid4()), name=name, comment_type="long",
                          is_active=active, admin_only=admin_only, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


def _save(w, slot, text="written"):
    return CommentGridSave(
        term_id=w["term"].id, sub_term_id=w["sub"].id, class_id=w["cls"].id,
        comment_type_id=slot.id,
        items=[CommentItem(student_id=w["pupil"].id, text=text)])


# ── ownership: the two rules, and no third ────────────────────────────────────

@pytest.mark.asyncio
async def test_a_default_slot_belongs_to_the_pc_teacher(db, org):
    w = await _world(db, org)
    slot = await _slot(db, org, "Form Teacher's Note", admin_only=False)

    res = await save_report_comments(_save(w, slot), db=db, current_user=w["teacher"])
    assert res["saved"] == 1

    row = (await db.execute(
        __import__("sqlalchemy").select(StudentReportComment))).scalars().one()
    assert row.comment_type_id == slot.id
    assert row.kind == "custom", "the slot identifies the row; kind is a literal"


@pytest.mark.asyncio
async def test_an_admin_only_slot_refuses_the_pc_teacher(db, org):
    """Like `head`. The refusal names the slot, so the teacher knows which one."""
    w = await _world(db, org)
    slot = await _slot(db, org, "Principal's Remark", admin_only=True)

    with pytest.raises(HTTPException) as e:
        await save_report_comments(_save(w, slot), db=db, current_user=w["teacher"])
    assert e.value.status_code == 403
    assert "Principal's Remark" in str(e.value.detail)


@pytest.mark.asyncio
async def test_an_admin_may_write_either_kind_of_slot(db, org):
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    for name, admin_only in (("Principal's Remark", True), ("Form Teacher's Note", False)):
        slot = await _slot(db, org, name, admin_only=admin_only)
        res = await save_report_comments(_save(w, slot), db=db, current_user=admin)
        assert res["saved"] == 1


@pytest.mark.asyncio
async def test_a_teacher_who_is_not_the_pc_teacher_is_refused(db, org):
    w = await _world(db, org)
    slot = await _slot(db, org, "Form Teacher's Note", admin_only=False)
    intruder = await _user(db, org, "teacher")

    with pytest.raises(HTTPException) as e:
        await save_report_comments(_save(w, slot), db=db, current_user=intruder)
    assert e.value.status_code == 403
    assert "PC teacher" in str(e.value.detail)


# ── the built-ins are untouched ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_the_built_in_slots_behave_exactly_as_before(db, org):
    """A request with no comment_type_id must be indistinguishable from the old
    behaviour: head admin-only, pc to the class's PC teacher."""
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")

    head = CommentGridSave(term_id=w["term"].id, sub_term_id=w["sub"].id,
                           class_id=w["cls"].id, kind="head",
                           items=[CommentItem(student_id=w["pupil"].id, text="head text")])
    with pytest.raises(HTTPException) as e:
        await save_report_comments(head, db=db, current_user=w["teacher"])
    assert e.value.status_code == 403
    assert (await save_report_comments(head, db=db, current_user=admin))["saved"] == 1

    pc = CommentGridSave(term_id=w["term"].id, sub_term_id=w["sub"].id,
                         class_id=w["cls"].id, kind="pc",
                         items=[CommentItem(student_id=w["pupil"].id, text="pc text")])
    assert (await save_report_comments(pc, db=db, current_user=w["teacher"]))["saved"] == 1

    rows = (await db.execute(
        __import__("sqlalchemy").select(StudentReportComment))).scalars().all()
    assert {r.kind for r in rows} == {"head", "pc"}
    assert all(r.comment_type_id is None for r in rows), "built-ins carry no slot"


# ── identity: the slot, never `kind` ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_slots_do_not_read_each_others_text(db, org):
    """Both rows carry kind='custom'. A grid that filtered on `kind` would show
    one slot's text under the other."""
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    a = await _slot(db, org, "Principal's Remark", admin_only=True)
    b = await _slot(db, org, "Form Teacher's Note", admin_only=False)

    await save_report_comments(_save(w, a, "from the principal"), db=db, current_user=admin)
    await save_report_comments(_save(w, b, "from the form teacher"), db=db, current_user=admin)

    grid_a = await report_comment_grid(
        class_id=w["cls"].id, term_id=w["term"].id, sub_term_id=w["sub"].id,
        comment_type_id=a.id, db=db, current_user=admin)
    grid_b = await report_comment_grid(
        class_id=w["cls"].id, term_id=w["term"].id, sub_term_id=w["sub"].id,
        comment_type_id=b.id, db=db, current_user=admin)

    assert grid_a.slot_name == "Principal's Remark"
    assert grid_a.rows[0].text == "from the principal"
    assert grid_b.slot_name == "Form Teacher's Note"
    assert grid_b.rows[0].text == "from the form teacher"


@pytest.mark.asyncio
async def test_saving_a_slot_twice_updates_rather_than_duplicating(db, org):
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    slot = await _slot(db, org, "Principal's Remark", admin_only=True)

    await save_report_comments(_save(w, slot, "first"), db=db, current_user=admin)
    await save_report_comments(_save(w, slot, "second"), db=db, current_user=admin)

    rows = (await db.execute(
        __import__("sqlalchemy").select(StudentReportComment))).scalars().all()
    assert len(rows) == 1
    assert rows[0].text == "second"


# ── a slot must be real, ours, and active ─────────────────────────────────────

@pytest.mark.asyncio
async def test_an_unknown_slot_is_refused(db, org):
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    payload = CommentGridSave(term_id=w["term"].id, sub_term_id=w["sub"].id,
                              class_id=w["cls"].id, comment_type_id=str(uuid.uuid4()),
                              items=[])
    with pytest.raises(HTTPException) as e:
        await save_report_comments(payload, db=db, current_user=admin)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_an_inactive_slot_is_refused_with_a_reason(db, org):
    """Deactivating a slot should stop new writes, and say so rather than 404 —
    the slot exists, it is simply closed."""
    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    slot = await _slot(db, org, "Retired Remark", admin_only=False, active=False)

    with pytest.raises(HTTPException) as e:
        await save_report_comments(_save(w, slot), db=db, current_user=admin)
    assert e.value.status_code == 422
    assert "not active" in str(e.value.detail)


# ── the card, and the subject max-length lookup ───────────────────────────────

@pytest.mark.asyncio
async def test_the_card_omits_a_slot_with_no_text(db, org):
    """A labelled blank row invites a parent to read meaning into the gap, and
    "nobody wrote one" is not a comment. Absent, not present-and-empty."""
    from app.routers.modules.platform import report_card

    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    filled = await _slot(db, org, "Principal's Remark", admin_only=True)
    blank = await _slot(db, org, "Bursar's Note", admin_only=True)

    await save_report_comments(_save(w, filled, "Well done this term."),
                               db=db, current_user=admin)
    await save_report_comments(_save(w, blank, "   "), db=db, current_user=admin)

    card = await report_card(student_id=w["pupil"].id, term_id=w["term"].id,
                             sub_term_id=w["sub"].id, db=db, current_user=admin)
    names = [sc.name for sc in card.slot_comments]
    assert names == ["Principal's Remark"]
    assert card.slot_comments[0].text == "Well done this term."
    assert "Bursar's Note" not in names, "whitespace-only is not a comment"


@pytest.mark.asyncio
async def test_the_card_keeps_the_two_built_in_comments_separate(db, org):
    """Every custom row carries kind='custom', so a card that keyed comments by
    `kind` alone would collapse them together and could overwrite head or pc."""
    from app.routers.modules.platform import report_card

    w = await _world(db, org)
    admin = await _user(db, org, "org_admin")
    slot = await _slot(db, org, "Principal's Remark", admin_only=True)

    await save_report_comments(
        CommentGridSave(term_id=w["term"].id, sub_term_id=w["sub"].id,
                        class_id=w["cls"].id, kind="head",
                        items=[CommentItem(student_id=w["pupil"].id, text="head text")]),
        db=db, current_user=admin)
    await save_report_comments(_save(w, slot, "slot text"), db=db, current_user=admin)

    card = await report_card(student_id=w["pupil"].id, term_id=w["term"].id,
                             sub_term_id=w["sub"].id, db=db, current_user=admin)
    assert card.head_comment == "head text"
    assert [sc.text for sc in card.slot_comments] == ["slot text"]


@pytest.mark.asyncio
async def test_subject_max_length_matches_the_whole_name_not_a_substring(db, org):
    """The old lookup searched for "subject" ANYWHERE in a name, so an unrelated
    slot could supply the cap for subject remarks."""
    from app.routers.modules.platform import _subject_comment_max_length

    decoy = ReportCommentType(id=str(uuid.uuid4()), name="Subjective Assessment",
                              comment_type="long", max_length=99, is_active=True,
                              admin_only=False, org_id=org.id)
    db.add(decoy)
    await db.commit()
    assert await _subject_comment_max_length(db, org.id) is None, (
        "a name merely containing 'subject' must not supply the cap")

    # "Subject Teacher Comment" is the name actually in use — test_subject_report_
    # comments relies on it, and narrowing to a single guessed name broke that.
    real = ReportCommentType(id=str(uuid.uuid4()), name="Subject Teacher Comment",
                             comment_type="long", max_length=500, is_active=True,
                             admin_only=False, org_id=org.id)
    db.add(real)
    await db.commit()
    assert await _subject_comment_max_length(db, org.id) == 500


@pytest.mark.asyncio
async def test_subject_max_length_ignores_an_inactive_slot(db, org):
    from app.routers.modules.platform import _subject_comment_max_length

    db.add(ReportCommentType(id=str(uuid.uuid4()), name="Subject Teacher Comment",
                             comment_type="long", max_length=500, is_active=False,
                             admin_only=False, org_id=org.id))
    await db.commit()
    assert await _subject_comment_max_length(db, org.id) is None

# ── the flag has to be REACHABLE, not merely enforced ────────────────────────
#
# `admin_only` shipped as a column, and `_gate_comment_access` read it, and no
# request could ever set it: it was absent from CommentTypeCreate, from
# CommentTypeUpdate and from CommentTypeResponse. So every slot an admin made
# was PC-teacher-writable, the opt-out was unusable, and the ownership tests
# above still passed because they construct the model directly and bypass the
# schema. These two drive the API instead.


@pytest.mark.asyncio
async def test_admin_only_survives_the_create_schema(db, org):
    """The flag an admin sets at creation must reach the row and come back."""
    from app.routers.modules.platform import create_comment_type
    from app.schemas.platform import CommentTypeCreate

    admin = await _user(db, org, "org_admin")

    plain = await create_comment_type(
        CommentTypeCreate(name="Form Tutor Note", comment_type="short"), db, admin)
    assert plain.admin_only is False, "a slot is PC-teacher-writable by default"

    locked = await create_comment_type(
        CommentTypeCreate(name="Principal Endorsement", comment_type="long",
                          admin_only=True), db, admin)
    assert locked.admin_only is True, "the response must carry the flag back"

    row = (await db.execute(select(ReportCommentType).where(
        ReportCommentType.id == locked.id))).scalar_one()
    assert row.admin_only is True, "and it must be what was persisted"


@pytest.mark.asyncio
async def test_admin_only_can_be_handed_back_and_forth(db, org):
    """A slot's owner is not frozen at creation — PATCH moves it either way."""
    from app.routers.modules.platform import create_comment_type, update_comment_type
    from app.schemas.platform import CommentTypeCreate, CommentTypeUpdate

    admin = await _user(db, org, "org_admin")
    slot = await create_comment_type(
        CommentTypeCreate(name="Pastoral Summary", comment_type="long"), db, admin)

    locked = await update_comment_type(
        slot.id, CommentTypeUpdate(admin_only=True), db, admin)
    assert locked.admin_only is True

    # Toggling something else must not quietly reset ownership, which is what
    # exclude_unset is protecting.
    renamed = await update_comment_type(
        slot.id, CommentTypeUpdate(is_active=False), db, admin)
    assert renamed.admin_only is True, "an unrelated PATCH must not clear the flag"

    freed = await update_comment_type(
        slot.id, CommentTypeUpdate(admin_only=False), db, admin)
    assert freed.admin_only is False
