"""seed: school days per term + starter clubs/sports with memberships

Data-only, idempotent. Only fills gaps — never overwrites a value an admin set.
 * term_periods.total_days: Half-Term 30 / Full-Term 60 school days for every
   (session, term, sub-term) that has none (13-week Nigerian term, British
   calendar: ~65 weekdays minus public holidays and the mid-term break).
 * Clubs & sports (Robotics, Dance, Karate, ...) created per org if missing, and
   each active student without any membership gets 1-2 clubs (approved).
All values are editable in Report Setup / Clubs.

Revision ID: 144_seed_term_days_and_clubs
Revises: 143_teacher_many_sections
"""
import hashlib
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "144_seed_term_days_and_clubs"
down_revision = "143_teacher_many_sections"
branch_labels = None
depends_on = None

HALF_TERM_DAYS = 30
FULL_TERM_DAYS = 60

CLUBS = [
    ("Robotics Club", "Build and program robots.", "Wednesday", "Robotics Lab"),
    ("Coding Club", "Learn to code through projects.", "Tuesday", "ICT Lab"),
    ("Dance Club", "Contemporary, Afrobeat and ballet.", "Thursday", "Hall"),
    ("Karate", "Martial arts and discipline.", "Friday", "Sports Hall"),
    ("Football", "Boys and girls football squads.", "Monday", "Field"),
    ("Basketball", "Training and inter-house games.", "Tuesday", "Court"),
    ("Swimming", "Technique and fitness.", "Friday", "Pool"),
    ("Drama Club", "Acting and stagecraft.", "Wednesday", "Hall"),
    ("Music Club", "Choir and instruments.", "Thursday", "Music Room"),
    ("Chess Club", "Strategy and tournaments.", "Monday", "Library"),
    ("Debate Club", "Public speaking and debate.", "Thursday", "Room 1"),
    ("Art Club", "Drawing, painting and craft.", "Wednesday", "Art Room"),
]


def _now():
    return datetime.now(timezone.utc)


def seed(conn) -> None:
    now = _now()
    # 1) school days per term
    rows = conn.execute(sa.text(
        "SELECT s.org_id, s.id AS sid, t.id AS tid, st.id AS stid, st.name AS stname "
        "FROM academic_sessions s "
        "JOIN academic_terms t ON t.org_id = s.org_id "
        "JOIN academic_sub_terms st ON st.org_id = s.org_id AND st.is_active = :t "
        "WHERE s.is_current = :t"), {"t": True}).fetchall()
    for org, sid, tid, stid, stname in rows:
        days = HALF_TERM_DAYS if "half" in (stname or "").lower() else FULL_TERM_DAYS
        existing = conn.execute(sa.text(
            "SELECT id, total_days FROM term_periods WHERE org_id=:o AND session_id=:s AND term_id=:t AND sub_term_id=:st"),
            {"o": org, "s": sid, "t": tid, "st": stid}).fetchone()
        if existing is None:
            conn.execute(sa.text(
                "INSERT INTO term_periods (id, org_id, session_id, term_id, sub_term_id, total_days, created_at, updated_at) "
                "VALUES (:id,:o,:s,:t,:st,:d,:n,:n)"),
                {"id": str(uuid.uuid4()), "o": org, "s": sid, "t": tid, "st": stid, "d": days, "n": now})
        elif existing[1] is None:
            conn.execute(sa.text("UPDATE term_periods SET total_days=:d WHERE id=:i"), {"d": days, "i": existing[0]})

    # 2) clubs + memberships (only orgs that actually have students)
    orgs = [r[0] for r in conn.execute(sa.text(
        "SELECT DISTINCT org_id FROM students WHERE is_deleted = :f"), {"f": False}).fetchall()]
    for org in orgs:
        club_ids = []
        for name, desc, day, loc in CLUBS:
            cid = conn.execute(sa.text(
                "SELECT id FROM clubs WHERE org_id=:o AND name=:n AND is_deleted=:f"),
                {"o": org, "n": name, "f": False}).scalar()
            if cid is None:
                cid = str(uuid.uuid4())
                conn.execute(sa.text(
                    "INSERT INTO clubs (id, org_id, name, description, meeting_day, meeting_time, location, is_active, "
                    "is_deleted, created_at, updated_at) VALUES (:id,:o,:n,:d,:day,:tm,:loc,:a,:f,:now,:now)"),
                    {"id": cid, "o": org, "n": name, "d": desc, "day": day, "tm": "3:30 PM", "loc": loc,
                     "a": True, "f": False, "now": now})
            club_ids.append(cid)
        sess = conn.execute(sa.text(
            "SELECT name FROM academic_sessions WHERE org_id=:o AND is_current=:t"), {"o": org, "t": True}).scalar()
        term = conn.execute(sa.text(
            "SELECT name FROM academic_terms WHERE org_id=:o AND is_active=:t"), {"o": org, "t": True}).scalar()
        students = [r[0] for r in conn.execute(sa.text(
            "SELECT id FROM students WHERE org_id=:o AND is_deleted=:f AND id NOT IN "
            "(SELECT student_id FROM club_memberships WHERE org_id=:o)"), {"o": org, "f": False}).fetchall()]
        for stu in students:
            h = int(hashlib.sha256(stu.encode()).hexdigest(), 16)
            picks = {h % len(club_ids)}
            if h % 3:  # two thirds of students join a second club
                picks.add((h // 7) % len(club_ids))
            for i in picks:
                conn.execute(sa.text(
                    "INSERT INTO club_memberships (id, org_id, club_id, student_id, joined_at, role, is_active, status, "
                    "academic_year, term, created_at, updated_at) "
                    "VALUES (:id,:o,:c,:s,:now,'member',:a,'approved',:y,:t,:now,:now)"),
                    {"id": str(uuid.uuid4()), "o": org, "c": club_ids[i], "s": stu, "now": now, "a": True,
                     "y": sess, "t": (term or "").upper() or None})


def upgrade() -> None:
    seed(op.get_bind())


def downgrade() -> None:
    pass  # data-only seed; nothing to undo safely
