"""Tests for the CBT Question Bank (Phase A) — /cbt/question-bank + compose.

Proves the reusable bank + test composition + bulk import, and the RBAC boundary
that keeps students (who hold school:cbt:* to sit tests) out of the bank's answers.
"""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile
from sqlalchemy import select

from app.models.user import User, UserStatus
from app.models.role import Role, SCHOOL_PERMISSION_PRESETS
from app.models.modules.school import QuestionBankItem, CBTExam, CBTQuestion, Subject, ExamStatus
from app.routers.modules.cbt import (
    list_bank, create_bank_item, update_bank_item, delete_bank_item,
    import_bank, add_questions_from_bank,
)
from app.schemas.question_bank import BankItemCreate, BankItemUpdate, ComposeFromBank

pytestmark = pytest.mark.asyncio


async def _preset_user(db, org, slug) -> User:
    u = User(id=str(uuid.uuid4()), email=f"{slug}-{uuid.uuid4().hex[:6]}@example.com",
             full_name=slug.title(), status=UserStatus.ACTIVE, org_id=org.id)
    role = Role(id=str(uuid.uuid4()), name=slug, slug=f"{slug}-{uuid.uuid4().hex[:6]}",
                permissions=list(SCHOOL_PERMISSION_PRESETS[slug]), org_id=org.id, is_system=False)
    db.add(role)
    u.roles = [role]
    db.add(u)
    await db.commit()
    return u


async def _subject(db, org, name="Mathematics", code="MTH") -> Subject:
    s = Subject(id=str(uuid.uuid4()), name=name, code=code, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def _exam(db, org, teacher) -> CBTExam:
    e = CBTExam(id=str(uuid.uuid4()), title="Midterm", created_by=teacher.id, org_id=org.id,
                status=ExamStatus.DRAFT, total_points=0)
    db.add(e)
    await db.commit()
    return e


def _csv(text: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(text.encode("utf-8")), filename="q.csv",
                      headers=Headers({"content-type": "text/csv"}))


# ── Create / validate ────────────────────────────────────────────────────────────

async def test_create_persists_and_roundtrips(db, org, teacher):
    subj = await _subject(db, org)
    resp = await create_bank_item(
        BankItemCreate(question_text="2+2?", question_type="mcq", subject_id=subj.id,
                       topic="Arithmetic", difficulty="easy",
                       options=[{"key": "a", "text": "4"}, {"key": "b", "text": "5"}],
                       correct_answer="a", points=2),
        request=None, db=db, current_user=teacher,
    )
    assert resp["question_type"] == "mcq" and resp["difficulty"] == "easy"
    assert resp["subject_name"] == "Mathematics" and resp["topic"] == "Arithmetic" and resp["points"] == 2
    row = (await db.execute(select(QuestionBankItem).where(QuestionBankItem.id == resp["id"]))).scalar_one()
    assert row.question_text == "2+2?"


async def test_create_validation(db, org, teacher):
    with pytest.raises(HTTPException) as e1:
        await create_bank_item(BankItemCreate(question_text="q", difficulty="trivial"), request=None, db=db, current_user=teacher)
    assert e1.value.status_code == 422
    with pytest.raises(HTTPException) as e2:
        await create_bank_item(BankItemCreate(question_text="q", question_type="essay"), request=None, db=db, current_user=teacher)
    assert e2.value.status_code == 422
    with pytest.raises(HTTPException) as e3:
        await create_bank_item(BankItemCreate(question_text="q", subject_id=str(uuid.uuid4())), request=None, db=db, current_user=teacher)
    assert e3.value.status_code == 404


# ── List + filters ────────────────────────────────────────────────────────────────

async def test_list_and_filters(db, org, teacher):
    subj = await _subject(db, org)
    await create_bank_item(BankItemCreate(question_text="Algebra q", subject_id=subj.id, difficulty="hard", topic="Algebra"), request=None, db=db, current_user=teacher)
    await create_bank_item(BankItemCreate(question_text="Geometry q", difficulty="easy", topic="Geometry"), request=None, db=db, current_user=teacher)
    allres = await list_bank(page=1, page_size=50, subject_id=None, topic=None, difficulty=None, question_type=None, search=None, db=db, current_user=teacher)
    assert allres["total"] == 2
    by_subj = await list_bank(page=1, page_size=50, subject_id=subj.id, topic=None, difficulty=None, question_type=None, search=None, db=db, current_user=teacher)
    assert by_subj["total"] == 1 and by_subj["items"][0]["topic"] == "Algebra"
    by_diff = await list_bank(page=1, page_size=50, subject_id=None, topic=None, difficulty="easy", question_type=None, search=None, db=db, current_user=teacher)
    assert by_diff["total"] == 1 and by_diff["items"][0]["topic"] == "Geometry"
    by_search = await list_bank(page=1, page_size=50, subject_id=None, topic=None, difficulty=None, question_type=None, search="Algebra", db=db, current_user=teacher)
    assert by_search["total"] == 1


# ── Update / delete ────────────────────────────────────────────────────────────────

async def test_update_and_delete(db, org, teacher):
    item = await create_bank_item(BankItemCreate(question_text="q", difficulty="easy"), request=None, db=db, current_user=teacher)
    upd = await update_bank_item(item["id"], BankItemUpdate(difficulty="hard", question_type="true_false", points=3), request=None, db=db, current_user=teacher)
    assert upd["difficulty"] == "hard" and upd["question_type"] == "true_false" and upd["points"] == 3
    await delete_bank_item(item["id"], request=None, db=db, current_user=teacher)
    gone = (await db.execute(select(QuestionBankItem).where(QuestionBankItem.id == item["id"]))).scalar_one_or_none()
    assert gone is None


# ── Import (CSV) ────────────────────────────────────────────────────────────────────

async def test_import_csv(db, org, teacher):
    await _subject(db, org, name="Mathematics", code="MTH")
    csv_text = (
        "question,type,subject,topic,difficulty,option_a,option_b,correct_answer,points\n"
        "What is 2+2?,mcq,Mathematics,Arithmetic,easy,4,5,a,2\n"
        "Sky is blue,true_false,MTH,Nature,easy,,,true,1\n"
        ",mcq,Mathematics,,,,,,\n"  # missing question -> error, skipped
    )
    res = await import_bank(file=_csv(csv_text), request=None, db=db, current_user=teacher)
    assert res["imported"] == 2 and len(res["errors"]) == 1
    rows = (await db.execute(select(QuestionBankItem).where(QuestionBankItem.org_id == org.id))).scalars().all()
    assert len(rows) == 2
    math_q = next(r for r in rows if r.question_text == "What is 2+2?")
    assert math_q.subject_id is not None and math_q.difficulty == "easy"
    assert math_q.options == [{"key": "a", "text": "4"}, {"key": "b", "text": "5"}]


# ── Compose from bank ────────────────────────────────────────────────────────────────

async def test_from_bank_copies_to_exam(db, org, teacher):
    exam = await _exam(db, org, teacher)
    q1 = await create_bank_item(BankItemCreate(question_text="q1", points=2), request=None, db=db, current_user=teacher)
    q2 = await create_bank_item(BankItemCreate(question_text="q2", points=3), request=None, db=db, current_user=teacher)
    res = await add_questions_from_bank(exam.id, ComposeFromBank(question_ids=[q1["id"], q2["id"]]),
                                        request=None, db=db, current_user=teacher)
    assert res["added"] == 2 and res["total_points"] == 5
    exam_qs = (await db.execute(select(CBTQuestion).where(CBTQuestion.exam_id == exam.id))).scalars().all()
    assert len(exam_qs) == 2
    # copies are independent — deleting the bank item leaves the exam question intact
    await delete_bank_item(q1["id"], request=None, db=db, current_user=teacher)
    still = (await db.execute(select(CBTQuestion).where(CBTQuestion.exam_id == exam.id))).scalars().all()
    assert len(still) == 2


# ── RBAC: bank is staff-only (students hold cbt:* but NOT school:* — no answer leak) ──

async def test_bank_rbac_excludes_students(db, org):
    for slug in ("manager", "teacher"):
        u = await _preset_user(db, org, slug)
        assert u.has_permission("school:read") and u.has_permission("school:write")
    student = await _preset_user(db, org, "student")
    assert student.has_permission("school:cbt:read") and student.has_permission("school:cbt:write")
    assert not student.has_permission("school:read") and not student.has_permission("school:write")
