"""Messenger module — conversations, messages, uploads, WebSocket.

Endpoints
---------
  GET    /messenger/conversations                — list conversations I belong to
  POST   /messenger/conversations                — create direct (or group) conv
  GET    /messenger/messages/{conversation_id}   — paginated history
  POST   /messenger/messages                     — send a message (REST fallback)
  POST   /messenger/upload                       — upload image/video, returns URL
  WS     /messenger/ws                           — real-time message broadcast

WebSocket protocol
------------------
* Client connects to ``/messenger/ws?token=<access_token>``.
* On connect, the server validates the JWT, pins the user/org, and joins the
  per-org broadcast pool.
* Every message the user sends (via POST or WS frame) is broadcast to all
  members of the conversation who are currently connected.
* Client-sent WS frames are JSON: ``{"conversation_id": "...", "type": "text",
  "content": "..."}``. The server persists, then broadcasts the full
  ``MessageResponse`` envelope to recipients.

Tenant scoping
--------------
Every row is filtered by ``current_user.org_id``. The "global org" room is
a special ``Conversation`` with ``kind=global`` that's lazily created on
first access so new orgs don't need a migration step.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, UploadFile, File,
    WebSocket, WebSocketDisconnect, status,
)
from jose import JWTError
from sqlalchemy import select, or_, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.core.security import decode_token
from app.database import get_db, AsyncSessionLocal
from app.deps import get_current_active_user
from app.models.user import User, UserStatus
from app.models.messenger import (
    Conversation, ConversationMember, Message,
    ConversationKind, MessageType,
)
from app.schemas.messenger import (
    ConversationCreate, ConversationResponse, MemberSummary,
    MessageCreate, MessageResponse, UploadResponse,
)

logger = logging.getLogger("extracare.messenger")
settings = get_settings()
router = APIRouter(prefix="/messenger", tags=["Messenger"])


# ── Connection manager (in-process pub/sub) ─────────────────────────────────
#
# Single-worker assumption. Multi-worker deployments need Redis pub/sub —
# drop in `aioredis.PubSub` here and every broadcast becomes an org-scoped
# publish. Keeping the API shape future-proof so that swap is one file.

class ConnectionManager:
    def __init__(self) -> None:
        # org_id → set[ (user_id, WebSocket) ]
        self._pool: dict[str, set[tuple[str, WebSocket]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, org_id: str, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._pool.setdefault(org_id, set()).add((user_id, ws))

    async def disconnect(self, org_id: str, user_id: str, ws: WebSocket) -> None:
        async with self._lock:
            bucket = self._pool.get(org_id)
            if not bucket:
                return
            bucket.discard((user_id, ws))
            if not bucket:
                self._pool.pop(org_id, None)

    def _recipients(self, org_id: str, user_ids: Optional[set[str]]) -> list[WebSocket]:
        bucket = self._pool.get(org_id) or set()
        if user_ids is None:
            return [ws for _uid, ws in bucket]
        return [ws for uid, ws in bucket if uid in user_ids]

    async def broadcast(
        self,
        org_id: str,
        payload: dict,
        user_ids: Optional[set[str]] = None,
    ) -> None:
        """Send ``payload`` (json-serialisable) to every live socket in ``org_id``.

        If ``user_ids`` is provided, only those users receive the frame —
        used for DMs and group chats. ``None`` means "everyone in the org"
        (global room).
        """
        text = json.dumps(payload, default=str)
        dead: list[tuple[str, WebSocket]] = []
        for ws in self._recipients(org_id, user_ids):
            try:
                await ws.send_text(text)
            except Exception:
                # Client disconnected mid-broadcast; reap below so the pool
                # doesn't grow stale sockets.
                dead.append(("", ws))
        if dead:
            async with self._lock:
                bucket = self._pool.get(org_id)
                if bucket:
                    for _uid, ws in dead:
                        bucket.discard((_uid, ws))


manager = ConnectionManager()


# ── Helpers ─────────────────────────────────────────────────────────────────

def _dm_pair_key(a: str, b: str) -> str:
    return ":".join(sorted([a, b]))


def _member_summary(u: User) -> MemberSummary:
    return MemberSummary(
        id=u.id,
        full_name=u.full_name,
        email=u.email,
        avatar_url=getattr(u, "avatar_url", None),
    )


async def _members_for(db: AsyncSession, conv: Conversation) -> list[MemberSummary]:
    """Resolve displayable members for a conversation.

    ``global`` rooms have an implicit membership (every user in the org),
    so we fetch up to 50 active users for the header summary instead of
    materialising a 500-row `conversation_members` table.
    """
    if conv.kind == ConversationKind.GLOBAL:
        rows = (await db.execute(
            select(User).where(
                User.org_id == conv.org_id,
                User.is_deleted == False,
                User.status == UserStatus.ACTIVE,
            ).limit(50)
        )).scalars().all()
        return [_member_summary(u) for u in rows]

    # Explicit membership for direct/group.
    out: list[MemberSummary] = []
    for m in conv.members:
        if m.user and not m.user.is_deleted:
            out.append(_member_summary(m.user))
    return out


async def _member_ids(db: AsyncSession, conv: Conversation) -> set[str]:
    """User IDs that should receive broadcasts for this conversation."""
    if conv.kind == ConversationKind.GLOBAL:
        rows = (await db.execute(
            select(User.id).where(
                User.org_id == conv.org_id,
                User.is_deleted == False,
            )
        )).scalars().all()
        return set(rows)
    return {m.user_id for m in conv.members}


async def _conversation_preview(db: AsyncSession, conv: Conversation) -> tuple[Optional[datetime], Optional[str]]:
    """Return (last_message_at, preview) for the list view."""
    row = (await db.execute(
        select(Message.created_at, Message.content, Message.type)
        .where(Message.conversation_id == conv.id, Message.is_deleted == False)
        .order_by(desc(Message.created_at))
        .limit(1)
    )).first()
    if not row:
        return (None, None)
    created_at, content, mtype = row
    if mtype == MessageType.TEXT:
        preview = (content or "")[:140]
    elif mtype == MessageType.IMAGE:
        preview = "📷 Image"
    elif mtype == MessageType.VIDEO:
        preview = "🎬 Video"
    else:
        preview = ""
    return (created_at, preview)


async def _to_conv_response(db: AsyncSession, conv: Conversation) -> ConversationResponse:
    members = await _members_for(db, conv)
    last_at, preview = await _conversation_preview(db, conv)
    return ConversationResponse(
        id=conv.id,
        org_id=conv.org_id,
        kind=conv.kind,
        title=conv.title,
        members=members,
        last_message_at=last_at,
        last_message_preview=preview,
        created_at=conv.created_at,
    )


def _to_msg_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        org_id=m.org_id,
        sender_id=m.sender_id,
        sender_name=(m.sender.full_name if m.sender else None),
        sender_avatar_url=(getattr(m.sender, "avatar_url", None) if m.sender else None),
        type=m.type,
        content=m.content,
        file_url=m.file_url,
        created_at=m.created_at,
    )


async def _get_or_create_global(db: AsyncSession, org_id: str, creator_id: Optional[str] = None) -> Conversation:
    row = (await db.execute(
        select(Conversation).where(
            Conversation.org_id == org_id,
            Conversation.kind == ConversationKind.GLOBAL,
        )
    )).scalar_one_or_none()
    if row:
        return row
    conv = Conversation(
        org_id=org_id,
        kind=ConversationKind.GLOBAL,
        title="Organisation-wide",
        created_by=creator_id,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def _authorize_conversation(db: AsyncSession, conv_id: str, user: User) -> Conversation:
    """Load a conversation if the user may access it, else raise 404/403."""
    conv = (await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .where(Conversation.id == conv_id, Conversation.org_id == user.org_id)
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation not found for id: {conv_id}")
    if conv.kind != ConversationKind.GLOBAL:
        member_ids = {m.user_id for m in conv.members}
        if user.id not in member_ids:
            raise HTTPException(status_code=403, detail="Not a member of this conversation.")
    return conv


# ── REST: Conversations ─────────────────────────────────────────────────────

@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List every conversation visible to the caller within their org.

    The global room is auto-provisioned on first access so every org always
    has at least one entry, without requiring a migration or signup hook.
    """
    await _get_or_create_global(db, current_user.org_id, current_user.id)
    await db.flush()

    global_rows = (await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .where(
            Conversation.org_id == current_user.org_id,
            Conversation.kind == ConversationKind.GLOBAL,
        )
    )).scalars().all()

    # Direct/group: only those where the current user is an explicit member.
    membership_rows = (await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
        .where(
            Conversation.org_id == current_user.org_id,
            Conversation.kind != ConversationKind.GLOBAL,
            ConversationMember.user_id == current_user.id,
        )
    )).scalars().unique().all()

    out: list[ConversationResponse] = []
    for conv in list(global_rows) + list(membership_rows):
        out.append(await _to_conv_response(db, conv))
    # Sort: most recent activity first, global pinned-ish up top by default.
    out.sort(key=lambda c: (c.kind != ConversationKind.GLOBAL, -(c.last_message_at.timestamp() if c.last_message_at else 0)))
    return out


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if data.kind == ConversationKind.GLOBAL:
        raise HTTPException(status_code=400, detail="Global conversations are auto-provisioned; do not create manually.")

    if data.kind == ConversationKind.DIRECT:
        if not data.peer_id or data.peer_id == current_user.id:
            raise HTTPException(status_code=422, detail="peer_id: required and must be a different user")
        peer = (await db.execute(
            select(User).where(
                User.id == data.peer_id,
                User.org_id == current_user.org_id,
                User.is_deleted == False,
            )
        )).scalar_one_or_none()
        if not peer:
            raise HTTPException(status_code=404, detail="peer_id: user not found in your organisation")

        pair = _dm_pair_key(current_user.id, peer.id)
        existing = (await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(
                Conversation.org_id == current_user.org_id,
                Conversation.kind == ConversationKind.DIRECT,
                Conversation.dm_pair_key == pair,
            )
        )).scalar_one_or_none()
        if existing:
            return await _to_conv_response(db, existing)

        conv = Conversation(
            org_id=current_user.org_id,
            kind=ConversationKind.DIRECT,
            dm_pair_key=pair,
            created_by=current_user.id,
        )
        db.add(conv)
        await db.flush()
        db.add_all([
            ConversationMember(conversation_id=conv.id, user_id=current_user.id),
            ConversationMember(conversation_id=conv.id, user_id=peer.id),
        ])
        await db.flush()
        # Re-fetch with members eager-loaded for the response.
        conv = (await db.execute(
            select(Conversation)
            .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
            .where(Conversation.id == conv.id)
        )).scalar_one()
        return await _to_conv_response(db, conv)

    # kind=group
    ids = set(data.member_ids or [])
    ids.add(current_user.id)
    if len(ids) < 2:
        raise HTTPException(status_code=422, detail="member_ids: need at least one peer")
    valid = (await db.execute(
        select(User.id).where(
            User.id.in_(ids),
            User.org_id == current_user.org_id,
            User.is_deleted == False,
        )
    )).scalars().all()
    if set(valid) != ids:
        raise HTTPException(status_code=422, detail="member_ids: contains users outside your organisation")

    conv = Conversation(
        org_id=current_user.org_id,
        kind=ConversationKind.GROUP,
        title=data.title or f"Group ({len(ids)})",
        created_by=current_user.id,
    )
    db.add(conv)
    await db.flush()
    db.add_all([ConversationMember(conversation_id=conv.id, user_id=uid) for uid in ids])
    await db.flush()
    conv = (await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.members).selectinload(ConversationMember.user))
        .where(Conversation.id == conv.id)
    )).scalar_one()
    return await _to_conv_response(db, conv)


# ── REST: Messages ──────────────────────────────────────────────────────────

@router.get("/messages/{conversation_id}", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[datetime] = Query(default=None, description="Return messages strictly older than this ISO timestamp (pagination cursor)."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _authorize_conversation(db, conversation_id, current_user)
    q = select(Message).where(
        Message.conversation_id == conversation_id,
        Message.org_id == current_user.org_id,
        Message.is_deleted == False,
    )
    if before:
        q = q.where(Message.created_at < before)
    q = q.order_by(desc(Message.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    # Oldest-first for natural chat rendering.
    return [_to_msg_response(m) for m in reversed(rows)]


@router.post("/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conv = await _authorize_conversation(db, data.conversation_id, current_user)
    if data.type == MessageType.TEXT and not (data.content and data.content.strip()):
        raise HTTPException(status_code=422, detail="content: required for text messages")
    if data.type in (MessageType.IMAGE, MessageType.VIDEO) and not data.file_url:
        raise HTTPException(status_code=422, detail="file_url: required for media messages")

    msg = Message(
        org_id=current_user.org_id,
        conversation_id=conv.id,
        sender_id=current_user.id,
        type=data.type,
        content=data.content,
        file_url=data.file_url,
    )
    db.add(msg)
    await db.flush()
    # Re-fetch with sender joined for response.
    msg = (await db.execute(
        select(Message).where(Message.id == msg.id)
    )).scalar_one()

    response = _to_msg_response(msg)
    recipients = await _member_ids(db, conv)
    # Broadcast (fire-and-forget so REST responses stay snappy).
    asyncio.create_task(manager.broadcast(
        current_user.org_id,
        {"event": "message.new", "message": response.model_dump(mode="json")},
        user_ids=recipients if conv.kind != ConversationKind.GLOBAL else None,
    ))
    return response


# ── REST: Upload ────────────────────────────────────────────────────────────

ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ALLOWED_VIDEO_MIMES = {"video/mp4", "video/webm", "video/quicktime"}


@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ctype = (file.content_type or "").lower()
    if ctype in ALLOWED_IMAGE_MIMES:
        mtype = MessageType.IMAGE
    elif ctype in ALLOWED_VIDEO_MIMES:
        mtype = MessageType.VIDEO
    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {ctype or 'unknown'}")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    # Tenant-scoped subfolder so files never cross org boundaries on disk.
    org_dir = Path(settings.UPLOAD_DIR) / current_user.org_id
    org_dir.mkdir(parents=True, exist_ok=True)

    # Strip path components from the client-supplied name; add UUID prefix so
    # uploads never collide and browsing the dir doesn't leak user patterns.
    orig = os.path.basename(file.filename or "upload.bin")
    ext = os.path.splitext(orig)[1].lower()
    fname = f"{uuid.uuid4().hex}{ext}"
    path = org_dir / fname

    size = 0
    with open(path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 64)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                out.close()
                try:
                    path.unlink()
                except OSError:
                    pass
                raise HTTPException(
                    status_code=413,
                    detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
                )
            out.write(chunk)

    # Public URL, served via StaticFiles mount at /uploads in main.py.
    file_url = f"/uploads/{current_user.org_id}/{fname}"
    logger.info("messenger.upload user=%s org=%s type=%s size=%s", current_user.id, current_user.org_id, mtype.value, size)
    return UploadResponse(file_url=file_url, type=mtype, size_bytes=size, filename=orig)


# ── WebSocket ───────────────────────────────────────────────────────────────

async def _auth_ws(token: str) -> Optional[User]:
    """Resolve a WebSocket token to an active User, or None if invalid.

    Returns None on any failure so the caller can close with 4401 — we don't
    leak details over the unauthenticated channel.
    """
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        uid = payload.get("sub")
        if not uid:
            return None
    except JWTError:
        return None

    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.id == uid, User.is_deleted == False)
        )).scalar_one_or_none()
        if not user or user.status != UserStatus.ACTIVE:
            return None
        return user


@router.websocket("/ws")
async def messenger_ws(
    ws: WebSocket,
    token: str = Query(..., description="JWT access token (same as REST)."),
):
    """Real-time channel for the caller's org.

    On connect we authenticate the JWT, register the socket in the per-org
    pool, then fan out any ``message.new`` events that get broadcast while
    it's alive. Clients may also send ``MessageCreate``-shaped JSON frames
    to post a message without a REST round-trip.
    """
    user = await _auth_ws(token)
    if not user:
        await ws.close(code=4401)
        return

    await ws.accept()
    await manager.connect(user.org_id, user.id, ws)
    logger.info("messenger.ws.connect user=%s org=%s", user.id, user.org_id)

    try:
        await ws.send_text(json.dumps({
            "event": "connected",
            "user_id": user.id,
            "org_id": user.org_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        }))
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_text(json.dumps({"event": "error", "detail": "invalid JSON"}))
                continue

            # Treat any frame as a send-message intent if it looks like one.
            conv_id = payload.get("conversation_id")
            if not conv_id:
                await ws.send_text(json.dumps({"event": "error", "detail": "conversation_id required"}))
                continue

            # Each frame gets its own session so the WS loop isn't holding
            # a long-lived transaction between user keystrokes.
            async with AsyncSessionLocal() as db:
                try:
                    conv = await _authorize_conversation(db, conv_id, user)
                except HTTPException as e:
                    await ws.send_text(json.dumps({"event": "error", "detail": e.detail}))
                    continue

                mtype_raw = (payload.get("type") or "text").lower()
                try:
                    mtype = MessageType(mtype_raw)
                except ValueError:
                    await ws.send_text(json.dumps({"event": "error", "detail": f"invalid type {mtype_raw}"}))
                    continue

                content = payload.get("content")
                file_url = payload.get("file_url")
                if mtype == MessageType.TEXT and not (content and str(content).strip()):
                    await ws.send_text(json.dumps({"event": "error", "detail": "content required"}))
                    continue
                if mtype in (MessageType.IMAGE, MessageType.VIDEO) and not file_url:
                    await ws.send_text(json.dumps({"event": "error", "detail": "file_url required"}))
                    continue

                msg = Message(
                    org_id=user.org_id,
                    conversation_id=conv.id,
                    sender_id=user.id,
                    type=mtype,
                    content=content,
                    file_url=file_url,
                )
                db.add(msg)
                await db.commit()
                await db.refresh(msg)
                msg = (await db.execute(
                    select(Message).where(Message.id == msg.id)
                )).scalar_one()
                response = _to_msg_response(msg)
                recipients = await _member_ids(db, conv)

            await manager.broadcast(
                user.org_id,
                {"event": "message.new", "message": response.model_dump(mode="json")},
                user_ids=recipients if conv.kind != ConversationKind.GLOBAL else None,
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("messenger.ws error for user=%s", user.id)
    finally:
        await manager.disconnect(user.org_id, user.id, ws)
        logger.info("messenger.ws.disconnect user=%s org=%s", user.id, user.org_id)
