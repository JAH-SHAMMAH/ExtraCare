"""Secondary Report parity S-1a: Comment types + Result Default Comments."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.modules.platform import GradingScale
from app.routers.modules.platform import (
    create_comment_type, list_comment_types, update_comment_type, delete_comment_type,
    create_default_comment, list_default_comments, update_default_comment, delete_default_comment,
)
from app.schemas.platform import (
    CommentTypeCreate, CommentTypeUpdate, DefaultCommentCreate, DefaultCommentUpdate,
)


pytestmark = pytest.mark.asyncio


async def _admin(db, org) -> User:
    u = User(id=str(uuid.uuid4()), email=f"a-{uuid.uuid4().hex[:6]}@x.com", full_name="Registrar",
             status=UserStatus.ACTIVE, org_id=org.id)
    u.roles = []
    db.add(u)
    await db.commit()
    return u


async def _scale(db, org, name="GRADING SCALE") -> GradingScale:
    s = GradingScale(id=str(uuid.uuid4()), name=name, scale_type="numeric", is_provisional=False, org_id=org.id)
    db.add(s)
    await db.commit()
    return s


async def test_comment_types(db, org):
    admin = await _admin(db, org)
    c = await create_comment_type(payload=CommentTypeCreate(name="Classroom Behaviour", comment_type="short"), db=db, current_user=admin)
    assert c.comment_type == "short" and c.is_active is True
    await create_comment_type(payload=CommentTypeCreate(name="Teacher's Comment", comment_type="long", max_length=5000), db=db, current_user=admin)
    assert len(await list_comment_types(db=db, current_user=admin)) == 2

    # Bad length type + duplicate guarded.
    with pytest.raises(HTTPException) as ei:
        await create_comment_type(payload=CommentTypeCreate(name="X", comment_type="epic"), db=db, current_user=admin)
    assert ei.value.status_code == 422
    with pytest.raises(HTTPException) as ei:
        await create_comment_type(payload=CommentTypeCreate(name="Classroom Behaviour"), db=db, current_user=admin)
    assert ei.value.status_code == 409

    c2 = await update_comment_type(c.id, CommentTypeUpdate(is_active=False), db=db, current_user=admin)
    assert c2.is_active is False
    await delete_comment_type(c.id, db=db, current_user=admin)
    assert len(await list_comment_types(db=db, current_user=admin)) == 1


async def test_result_default_comments(db, org):
    admin = await _admin(db, org)
    scale = await _scale(db, org)
    d = await create_default_comment(payload=DefaultCommentCreate(
        teacher_type="class", grading_scale_id=scale.id, year_group="YEAR 7",
        min_score=Decimal("70"), max_score=Decimal("79"), comment="A commendable performance."),
        db=db, current_user=admin)
    assert d.grading_scale_name == "GRADING SCALE" and d.teacher_type == "class"

    # Bad teacher_type + unknown scale rejected.
    with pytest.raises(HTTPException) as ei:
        await create_default_comment(payload=DefaultCommentCreate(teacher_type="wizard", comment="x"), db=db, current_user=admin)
    assert ei.value.status_code == 422
    with pytest.raises(HTTPException) as ei:
        await create_default_comment(payload=DefaultCommentCreate(teacher_type="head", grading_scale_id="nope", comment="x"), db=db, current_user=admin)
    assert ei.value.status_code == 422

    d2 = await update_default_comment(d.id, DefaultCommentUpdate(comment="Excellent and consistent."), db=db, current_user=admin)
    assert d2.comment == "Excellent and consistent."
    # Filters.
    assert len(await list_default_comments(teacher_type="class", grading_scale_id=None, year_group=None, db=db, current_user=admin)) == 1
    assert len(await list_default_comments(teacher_type="head", grading_scale_id=None, year_group=None, db=db, current_user=admin)) == 0
    assert len(await list_default_comments(teacher_type=None, grading_scale_id=None, year_group="YEAR 8", db=db, current_user=admin)) == 0

    await delete_default_comment(d.id, db=db, current_user=admin)
    assert len(await list_default_comments(teacher_type=None, grading_scale_id=None, year_group=None, db=db, current_user=admin)) == 0
