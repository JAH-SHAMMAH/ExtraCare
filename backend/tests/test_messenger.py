"""Tests for the Messenger module.

Covers the REST surface only — WebSocket behaviour sits on top of the same
service layer (`_authorize_conversation`, message persistence, broadcast
fan-out), which these tests exercise directly via REST.

  • Global room auto-provisions on first list; one per org.
  • DM create is idempotent (a+b == b+a).
  • Group create validates member ids stay inside the org.
  • Send → appears in history; text requires content, media requires file_url.
  • Outsider cannot read/send in a DM they're not a member of.
  • Tenant isolation: a user in org B can't see org A's conversations.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.models.user import User, UserStatus
from app.models.organization import Organization, IndustryType
from app.models.messenger import Conversation, ConversationKind, Message, MessageType
from app.routers.messenger import (
    list_conversations, create_conversation, list_messages, create_message,
    _authorize_conversation, _dm_pair_key,
)
from app.schemas.messenger import ConversationCreate, MessageCreate


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def second_user(db, org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="peer@example.com",
        full_name="Peer Two",
        status=UserStatus.ACTIVE,
        org_id=org.id,
    )
    db.add(u)
    await db.commit()
    return u


@pytest_asyncio.fixture
async def other_org(db) -> Organization:
    o = Organization(
        id=str(uuid.uuid4()),
        name="Other Org",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        industry=IndustryType.SCHOOL,
        modules_enabled=["school"],
    )
    db.add(o)
    await db.commit()
    return o


@pytest_asyncio.fixture
async def other_org_user(db, other_org) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email="outsider@example.com",
        full_name="Other Org User",
        status=UserStatus.ACTIVE,
        org_id=other_org.id,
    )
    db.add(u)
    await db.commit()
    return u


# ── Global room ──────────────────────────────────────────────────────────────

async def test_list_conversations_autocreates_global(db, teacher):
    convs = await list_conversations(db=db, current_user=teacher)
    assert len(convs) == 1
    assert convs[0].kind == ConversationKind.GLOBAL
    assert convs[0].org_id == teacher.org_id

    # Second call doesn't create a duplicate.
    convs2 = await list_conversations(db=db, current_user=teacher)
    assert len(convs2) == 1
    assert convs2[0].id == convs[0].id


async def test_cannot_create_global_directly(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_conversation(
            data=ConversationCreate(kind=ConversationKind.GLOBAL),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 400


# ── Direct messages ──────────────────────────────────────────────────────────

async def test_create_dm_is_idempotent(db, teacher, second_user):
    first = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    # Same call from the other side should return the same conv.
    second = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=teacher.id),
        db=db, current_user=second_user,
    )
    assert first.id == second.id
    assert first.kind == ConversationKind.DIRECT
    assert {m.id for m in first.members} == {teacher.id, second_user.id}


async def test_dm_requires_peer_in_same_org(db, teacher, other_org_user):
    with pytest.raises(HTTPException) as exc:
        await create_conversation(
            data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=other_org_user.id),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 404


async def test_dm_rejects_self(db, teacher):
    with pytest.raises(HTTPException) as exc:
        await create_conversation(
            data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=teacher.id),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


def test_dm_pair_key_sorted():
    # Determinism — the pair key must not depend on call order.
    assert _dm_pair_key("b", "a") == _dm_pair_key("a", "b") == "a:b"


# ── Group ────────────────────────────────────────────────────────────────────

async def test_create_group_requires_peers_in_org(db, teacher, other_org_user):
    with pytest.raises(HTTPException) as exc:
        await create_conversation(
            data=ConversationCreate(
                kind=ConversationKind.GROUP,
                title="Cross-tenant",
                member_ids=[other_org_user.id],
            ),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_create_group_happy_path(db, teacher, second_user):
    conv = await create_conversation(
        data=ConversationCreate(
            kind=ConversationKind.GROUP,
            title="Weekly sync",
            member_ids=[second_user.id],
        ),
        db=db, current_user=teacher,
    )
    assert conv.kind == ConversationKind.GROUP
    assert conv.title == "Weekly sync"
    assert {m.id for m in conv.members} == {teacher.id, second_user.id}


# ── Messages ─────────────────────────────────────────────────────────────────

async def test_send_and_list_text_message(db, teacher, second_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    msg = await create_message(
        data=MessageCreate(conversation_id=dm.id, type=MessageType.TEXT, content="Hello!"),
        db=db, current_user=teacher,
    )
    assert msg.sender_id == teacher.id
    assert msg.content == "Hello!"
    assert msg.type == MessageType.TEXT

    history = await list_messages(
        conversation_id=dm.id, limit=50, before=None,
        db=db, current_user=second_user,
    )
    assert [m.content for m in history] == ["Hello!"]


async def test_text_requires_content(db, teacher, second_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await create_message(
            data=MessageCreate(conversation_id=dm.id, type=MessageType.TEXT, content="   "),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_media_requires_file_url(db, teacher, second_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await create_message(
            data=MessageCreate(conversation_id=dm.id, type=MessageType.IMAGE),
            db=db, current_user=teacher,
        )
    assert exc.value.status_code == 422


async def test_image_message_persists(db, teacher, second_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    msg = await create_message(
        data=MessageCreate(
            conversation_id=dm.id,
            type=MessageType.IMAGE,
            file_url="/uploads/org/abc.png",
        ),
        db=db, current_user=teacher,
    )
    assert msg.type == MessageType.IMAGE
    assert msg.file_url.endswith("abc.png")


# ── Authorisation ────────────────────────────────────────────────────────────

async def test_outsider_cannot_read_dm(db, teacher, second_user, unlinked_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    with pytest.raises(HTTPException) as exc:
        await _authorize_conversation(db, dm.id, unlinked_user)
    assert exc.value.status_code == 403


async def test_global_room_open_to_any_org_user(db, teacher, unlinked_user):
    # Listing as teacher creates the global room.
    convs = await list_conversations(db=db, current_user=teacher)
    global_id = next(c.id for c in convs if c.kind == ConversationKind.GLOBAL)

    # Unlinked user in the same org can read the global room.
    msg = await create_message(
        data=MessageCreate(conversation_id=global_id, type=MessageType.TEXT, content="Hi all"),
        db=db, current_user=unlinked_user,
    )
    assert msg.conversation_id == global_id
    history = await list_messages(
        conversation_id=global_id, limit=50, before=None,
        db=db, current_user=teacher,
    )
    assert [m.content for m in history] == ["Hi all"]


# ── Tenant isolation ─────────────────────────────────────────────────────────

async def test_other_org_user_cannot_see_conversation(db, teacher, second_user, other_org_user):
    dm = await create_conversation(
        data=ConversationCreate(kind=ConversationKind.DIRECT, peer_id=second_user.id),
        db=db, current_user=teacher,
    )
    # 404 (not 403) because we filter by org_id first — other tenants don't
    # even learn the conversation exists.
    with pytest.raises(HTTPException) as exc:
        await _authorize_conversation(db, dm.id, other_org_user)
    assert exc.value.status_code == 404


async def test_list_is_org_scoped(db, teacher, other_org_user):
    # Teacher (org A) creates nothing; global auto-provisions.
    convs_a = await list_conversations(db=db, current_user=teacher)
    assert all(c.org_id == teacher.org_id for c in convs_a)

    # Other org user sees only their own org's global room.
    convs_b = await list_conversations(db=db, current_user=other_org_user)
    assert all(c.org_id == other_org_user.org_id for c in convs_b)
    assert {c.id for c in convs_a}.isdisjoint({c.id for c in convs_b})
