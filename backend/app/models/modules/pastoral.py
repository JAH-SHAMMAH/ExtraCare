"""Pastoral, Boarding & Health models (Batch 4).

  • Hostel + BoardingAllocation — boarding houses and per-student bed allocation.
  • ExeatRequest — a boarder's request to leave campus; approval is a
    safety-sensitive action, so it carries explicit approver + decision fields.
  • MentorReport — a mentor's pastoral report on a mentee.
  • MedicalRecord — CONFIDENTIAL student health data, on its own ``medical:*``
    permission namespace (see role.py / workspace.py), never the broad school net.

All tenant-scoped; status/type stored as validated strings.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text, Date, DateTime, Integer, Boolean, ForeignKey, Index, UniqueConstraint

from app.models.base import Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin


class Hostel(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """A boarding house."""
    __tablename__ = "hostels"

    name = Column(String(120), nullable=False)
    gender = Column(String(20), nullable=True)        # boys | girls | mixed
    capacity = Column(Integer, nullable=True)
    warden_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_hostels_org", "org_id"),
    )


class BoardingAllocation(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's bed allocation in a hostel."""
    __tablename__ = "boarding_allocations"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    room = Column(String(40), nullable=True)
    bed = Column(String(40), nullable=True)
    allocated_on = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    allocated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_boarding_alloc_hostel_org", "hostel_id", "org_id"),
        Index("ix_boarding_alloc_student_org", "student_id", "org_id"),
    )


class ExeatRequest(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A boarder's request to leave campus. Authorising it is safety-sensitive,
    so the approver, decision time, and note are recorded explicitly (and audited
    at the router)."""
    __tablename__ = "exeat_requests"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    destination = Column(String(200), nullable=True)
    depart_at = Column(DateTime(timezone=True), nullable=True)
    expected_return_at = Column(DateTime(timezone=True), nullable=True)
    actual_return_at = Column(DateTime(timezone=True), nullable=True)
    # pending | approved | rejected | returned
    status = Column(String(20), default="pending", nullable=False)
    requested_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_note = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_exeat_org_status", "org_id", "status"),
        Index("ix_exeat_student_org", "student_id", "org_id"),
    )


class MentorReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A mentor's pastoral report on a mentee."""
    __tablename__ = "mentor_reports"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    term = Column(String(40), nullable=True)
    period = Column(String(60), nullable=True)
    summary = Column(Text, nullable=True)
    strengths = Column(Text, nullable=True)
    concerns = Column(Text, nullable=True)
    recommendations = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_mentor_reports_student_org", "student_id", "org_id"),
    )


class StudentMedicalRecord(Base, UUIDMixin, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """CONFIDENTIAL student health record. Gated by the ``medical:*`` namespace —
    never the broad school read. Soft-deleted to preserve the health history.

    Named ``StudentMedicalRecord`` (table ``student_medical_records``) to avoid
    colliding with the retained hospital-EMR ``MedicalRecord`` model.
    """
    __tablename__ = "student_medical_records"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    # visit | allergy | medication | immunization | condition | note
    record_type = Column(String(20), default="visit", nullable=False)
    title = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    treatment = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)       # low | medium | high
    recorded_on = Column(Date, nullable=True)
    follow_up_on = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_student_medical_records_student_org", "student_id", "org_id"),
        Index("ix_student_medical_records_org_type", "org_id", "record_type"),
    )


class PastoralSettings(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Per-org Pastoral configuration — the flag groups behind Pastoral Setup →
    Exeat Settings + Default Settings. One row per org (upserted). Mirrors the
    BehaviourSettings / ClubSettings pattern."""
    __tablename__ = "pastoral_settings"

    # ── Exeat Settings ────────────────────────────────────────────────────────
    enable_head_only_approval = Column(Boolean, default=False, nullable=False)
    notify_parent_on_exeat_approval = Column(Boolean, default=True, nullable=False)
    notify_house_parent_on_exeat_approval = Column(Boolean, default=False, nullable=False)
    notify_pastoral_head_on_new_request = Column(Boolean, default=True, nullable=False)

    # ── Default Settings ──────────────────────────────────────────────────────
    enable_tutorial_week = Column(Boolean, default=False, nullable=False)
    email_parent_on_new_point_entry = Column(Boolean, default=False, nullable=False)
    enable_academic_cohesion = Column(Boolean, default=False, nullable=False)
    show_award_in_point_analysis = Column(Boolean, default=False, nullable=False)
    allow_referral_in_mentor_comment = Column(Boolean, default=True, nullable=False)
    enable_point_category = Column(Boolean, default=False, nullable=False)
    enable_mentor_report_assessment = Column(Boolean, default=False, nullable=False)
    allow_only_merits_in_point_entry = Column(Boolean, default=False, nullable=False)
    allow_observation_in_mentor_comment = Column(Boolean, default=True, nullable=False)
    # "School Nurse Role" — points at an existing RBAC role (never a new one).
    school_nurse_role_id = Column(String(36), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)

    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, unique=True, index=True)


class HouseMaster(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A staff member assigned as master of a school house (Pastoral House Setup →
    House Masters). Reuses SchoolHouse; the person is a User."""
    __tablename__ = "house_masters"

    house_id = Column(String(36), ForeignKey("school_houses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_house_masters_house", "house_id", "org_id"),
    )


class HouseWeek(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A named pastoral 'house week' window (Pastoral House Setup → House Week
    Management). Used to scope house duty/roll-call periods."""
    __tablename__ = "house_weeks"

    name = Column(String(120), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class StudentPastoralAssignment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student's pastoral assignment — mentor, house, and leader flag (the
    Pastoral Students roster). One row per student per org. House reuses
    SchoolHouse; mentor is a User. Kept separate from the academic Student record."""
    __tablename__ = "student_pastoral_assignments"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    house_id = Column(String(36), ForeignKey("school_houses.id", ondelete="SET NULL"), nullable=True, index=True)
    mentor_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    is_leader = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "student_id", name="uq_student_pastoral_org_student"),
    )


class PointType(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A defined pastoral point type (Point System Setup). Conduct points are
    recorded against the Recognition ledger; this just defines the pickable types
    (e.g. 'Opening Point' sessional max 60, 'Reading' weekly max 10)."""
    __tablename__ = "point_types"

    name = Column(String(120), nullable=False)
    scope = Column(String(20), default="weekly", nullable=False)   # sessional | weekly
    max_point = Column(Integer, nullable=True)
    category = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class AwardType(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A defined award band (Award System Setup) — a point range that earns an
    award (e.g. 'Best in Neatness' min 2 max 10). Awards themselves are Recognition
    rows (type=academic_award)."""
    __tablename__ = "award_types"

    name = Column(String(120), nullable=False)
    min_point = Column(Integer, nullable=True)
    max_point = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


# ── Batch D: Hostel deepening (Setup config) ─────────────────────────────────

class HostelManager(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A staff member assigned to run a hostel (Hostel Setup → Managers). Parallels
    HouseMaster but for boarding houses. Distinct from the hostel's single warden."""
    __tablename__ = "hostel_managers"

    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("org_id", "hostel_id", "user_id", name="uq_hostel_manager"),
    )


class HostelLifeGrade(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A grade on the hostel-life scale (Hostel Setup → Life Grades), e.g.
    Excellent / Good / Fair / Poor. Consumed by hostel life comments (Batch D-2)."""
    __tablename__ = "hostel_life_grades"

    name = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class HostelCommentBank(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A reusable hostel-life comment template (Hostel Setup → Comment Bank), so
    managers pick a phrase instead of retyping. Optionally categorised."""
    __tablename__ = "hostel_comment_bank"

    text = Column(Text, nullable=False)
    category = Column(String(80), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


# ── Batch D-2: Hostel life comments + reports ────────────────────────────────

class HostelLifeComment(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A manager's per-boarder hostel-life note for a term, optionally carrying a
    grade off the HostelLifeGrade scale. The Result View aggregates these."""
    __tablename__ = "hostel_life_comments"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="SET NULL"), nullable=True, index=True)
    term = Column(String(60), nullable=True)
    grade = Column(String(80), nullable=True)      # matches a HostelLifeGrade.name
    comment = Column(Text, nullable=True)
    recorded_on = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_hostel_life_comments_student_org", "student_id", "org_id"),
    )


class HostelReport(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A hostel report — daily (roll/notes for a date) or manager (periodic
    summary). One table discriminated by ``report_type``."""
    __tablename__ = "hostel_reports"

    report_type = Column(String(20), default="daily", nullable=False)   # daily | manager
    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    report_date = Column(Date, nullable=True)
    title = Column(String(200), nullable=True)
    body = Column(Text, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_hostel_reports_type_org", "report_type", "org_id"),
    )


# ── Batch E: Discipline (Disciplinary Setup + Behaviour & Sanction) ──────────

class SanctionGroup(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A grouping of disciplinary actions (Disciplinary Setup → Sanction Group),
    e.g. 'Minor', 'Major', 'Boarding'."""
    __tablename__ = "sanction_groups"

    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class DisciplinaryAction(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A catalogue disciplinary action / sanction (Disciplinary Setup → Actions),
    e.g. 'Verbal Warning', 'Detention', 'Suspension'. Optionally in a group."""
    __tablename__ = "disciplinary_actions"

    name = Column(String(120), nullable=False)
    sanction_group_id = Column(String(36), ForeignKey("sanction_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    severity = Column(String(20), default="minor", nullable=False)   # minor | major | severe
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class DisciplinaryCommittee(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A named disciplinary committee (Disciplinary Setup → Committee), with staff
    members. Cases can be assigned to a committee."""
    __tablename__ = "disciplinary_committees"

    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class DisciplinaryCommitteeMember(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A staff member on a disciplinary committee, with an optional role label
    (e.g. 'Chair', 'Secretary')."""
    __tablename__ = "disciplinary_committee_members"

    committee_id = Column(String(36), ForeignKey("disciplinary_committees.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_label = Column(String(80), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "committee_id", "user_id", name="uq_committee_member"),
    )


class StudentDisciplinaryCase(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A disciplinary case against a STUDENT (Behaviour & Sanction): the offence,
    the sanction/action applied, the handling committee, and a status. Distinct
    from hr_extended.DisciplinaryCase, which is the STAFF disciplinary record."""
    __tablename__ = "student_disciplinary_cases"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    committee_id = Column(String(36), ForeignKey("disciplinary_committees.id", ondelete="SET NULL"), nullable=True, index=True)
    action_id = Column(String(36), ForeignKey("disciplinary_actions.id", ondelete="SET NULL"), nullable=True, index=True)
    sanction_group_id = Column(String(36), ForeignKey("sanction_groups.id", ondelete="SET NULL"), nullable=True)
    offence = Column(Text, nullable=True)
    sanction = Column(Text, nullable=True)         # free-text applied sanction / notes
    status = Column(String(20), default="pending", nullable=False)   # pending | resolved | dismissed
    case_date = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_student_disc_cases_student_org", "student_id", "org_id"),
        Index("ix_student_disc_cases_status_org", "status", "org_id"),
    )


# ── Batch F-1: Leadership Roles + Pastoral Heads ─────────────────────────────

class PastoralLeadershipRole(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A student pastoral-leadership role (Leadership Roles setup), e.g. Head Boy,
    House Captain, Prefect. A lightweight pastoral list — NOT an RBAC role."""
    __tablename__ = "pastoral_leadership_roles"

    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class PastoralHead(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A staff member holding a pastoral head position (Pastoral Heads setup), e.g.
    Head of Boarding, Head of Pastoral Care. Lightweight — NOT an RBAC role."""
    __tablename__ = "pastoral_heads"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    scope = Column(String(120), nullable=True)     # optional area, e.g. a house/section name
    is_active = Column(Boolean, default=True, nullable=False)


# ── Batch F-2: Roll Call + Pastoral Report + Remarks ─────────────────────────

class HostelRollCall(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A boarding roll-call mark for one boarder, on a date, for a session
    (morning|afternoon|evening|night). Distinct from the school-wide class
    AttendanceEvent — this is the pastoral/boarding presence check."""
    __tablename__ = "hostel_roll_calls"

    hostel_id = Column(String(36), ForeignKey("hostels.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    roll_date = Column(Date, nullable=False, index=True)
    session = Column(String(20), default="evening", nullable=False)   # morning|afternoon|evening|night
    status = Column(String(20), default="present", nullable=False)    # present|absent|exeat|sick
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "student_id", "roll_date", "session", name="uq_roll_call"),
        Index("ix_roll_calls_hostel_date", "hostel_id", "roll_date"),
    )


class PastoralRemarkBank(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A reusable pastoral-report remark template (Pastoral Report Setup). Managers
    pick a phrase for the term remark instead of retyping."""
    __tablename__ = "pastoral_remark_bank"

    text = Column(Text, nullable=False)
    category = Column(String(80), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class PastoralRemark(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """A per-student pastoral remark for a term — the head/mentor's summary that
    tops the pastoral report."""
    __tablename__ = "pastoral_remarks"

    student_id = Column(String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term = Column(String(60), nullable=True)
    category = Column(String(80), nullable=True)
    remark = Column(Text, nullable=True)
    recorded_on = Column(Date, nullable=True)
    recorded_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_pastoral_remarks_student_org", "student_id", "org_id"),
    )
