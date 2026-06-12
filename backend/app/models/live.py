"""Live Session models — teacher-hosted livestreams.

A ``LiveSession`` is the persistent metadata for a room. The actual media
stream flows peer-to-peer via WebRTC; our backend only:

  1. Lets the host open / close the room (REST).
  2. Relays signaling messages (SDP offers/answers, ICE candidates) over a
     WebSocket so peers can discover each other through NAT.

Dropping WebRTC and falling back to a server-relayed WebSocket stream is
possible but out of scope for MVP — the model doesn't store media, only
who is hosting what.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin


class LiveSession(Base, UUIDMixin, TimestampMixin, TenantMixin):
    __tablename__ = "live_sessions"

    host_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    # Optional binding to a school class — lets us scope "who can watch"
    # once a class roster exists. For MVP any org member can join.
    class_id = Column(String(36), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True, index=True)
    # Optional bindings into the ERP timetable. When set, the session is
    # discoverable from the timetable slot ("join today's Maths lesson")
    # and viewer joins are mirrored into AttendanceRecord.
    subject_id = Column(String(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    timetable_id = Column(String(36), ForeignKey("timetables.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    host = relationship("User", lazy="joined")

    __table_args__ = (
        # Most common query: active sessions for an org.
        Index("ix_live_session_org_active", "org_id", "is_active"),
    )


class LiveRecording(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Uploaded recording of a session.

    We use client-side MediaRecorder on the host (WebRTC MVP doesn't have a
    media server to tee the stream to). The host uploads the final blob at
    session end — or in chunks if we later add resumable uploads.
    """
    __tablename__ = "live_recordings"

    session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    # Absolute-relative path inside UPLOAD_DIR. Keep small; the full URL is
    # built at serialisation time from settings + tenant scoping.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    duration_seconds = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)


class LiveAttendance(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """One row per viewer join. Updated with left_at on disconnect.

    Lets us answer "who watched, when, and for how long" — the baseline
    analytics a teacher expects for an online class.
    """
    __tablename__ = "live_attendance"

    session_id = Column(String(36), ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), nullable=False)
    left_at = Column(DateTime(timezone=True), nullable=True)
    # Computed on disconnect. Nullable while the viewer is still connected.
    duration_seconds = Column(Integer, nullable=True)

    __table_args__ = (
        # Analytics query: attendance for a session, ordered by joined_at.
        Index("ix_live_attendance_session_joined", "session_id", "joined_at"),
    )
