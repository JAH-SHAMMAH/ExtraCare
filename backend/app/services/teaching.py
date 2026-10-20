"""Teaching assignments: which teacher teaches which subject to which class.

Helpers shared by the Teaching Assignments page, Bulk Add Teachers and the Users
create form. `match_subject` turns what an admin types ("CRS", "ICT", "Biology")
into a real Subject row; `assign_subject_to_classes` records the assignments.
"""
from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modules.school import SchoolClass, Subject, TeachingAssignment

_STOP = {"and", "of", "the", "in", "for", "to", "&"}


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def _acronym(name: str) -> str:
    return "".join(w[0] for w in _norm(name).split() if w not in _STOP)


def match_subject(text: str | None, subjects: Iterable) -> tuple[object | None, str]:
    """(the Subject `text` names, or None) and a short reason when None.

    Tiers, first one with exactly ONE hit wins: exact name -> code -> acronym
    ("CRS" = Christian Religious Studies, "ICT" = Information and Communication
    Technology) -> the text as a whole word inside the name. Two hits in a tier
    means ambiguous, which is reported rather than guessed.
    """
    t = _norm(text)
    if not t:
        return None, "no subject given"
    subs = list(subjects)
    tiers = [
        [s for s in subs if _norm(s.name) == t],
        [s for s in subs if _norm(getattr(s, "code", None)) == t],
        [s for s in subs if len(t) >= 2 and " " not in t and _acronym(s.name) == t],
        [s for s in subs if len(t) >= 3 and re.search(rf"\b{re.escape(t)}\b", _norm(s.name))],
    ]
    for hits in tiers:
        if len(hits) == 1:
            return hits[0], ""
        if len(hits) > 1:
            return None, f"'{text}' matches more than one subject"
    return None, f"no subject called '{text}'"


async def classes_in_sections(db: AsyncSession, org_id: str, section_ids: Iterable[str]) -> list[SchoolClass]:
    ids = [i for i in section_ids if i]
    if not ids:
        return []
    return list((await db.execute(
        select(SchoolClass).where(SchoolClass.org_id == org_id, SchoolClass.section_id.in_(ids))
        .order_by(SchoolClass.name)
    )).scalars().all())


async def assign_subject_to_classes(db: AsyncSession, org_id: str, teacher_id: str,
                                    subject_id: str, class_ids: Iterable[str]) -> int:
    """Add (teacher, class, subject) rows that do not exist yet; returns how many were added."""
    wanted = list(dict.fromkeys(class_ids))
    if not wanted:
        return 0
    have = set((await db.execute(
        select(TeachingAssignment.class_id).where(
            TeachingAssignment.org_id == org_id, TeachingAssignment.teacher_id == teacher_id,
            TeachingAssignment.subject_id == subject_id, TeachingAssignment.class_id.in_(wanted),
        ))).scalars().all())
    added = 0
    for cid in wanted:
        if cid not in have:
            db.add(TeachingAssignment(org_id=org_id, teacher_id=teacher_id, class_id=cid, subject_id=subject_id))
            added += 1
    return added


async def assign_subjects_by_section(db: AsyncSession, org_id: str, teacher_id: str,
                                     subject_ids: Iterable[str]) -> int:
    """Teach each subject in EVERY class of that subject's own section (the sensible
    default for "Biology, Secondary"); the Teaching Assignments page narrows it."""
    subs = list((await db.execute(
        select(Subject).where(Subject.org_id == org_id, Subject.id.in_(list(subject_ids)))
    )).scalars().all())
    total = 0
    for s in subs:
        classes = await classes_in_sections(db, org_id, [s.section_id])
        total += await assign_subject_to_classes(db, org_id, teacher_id, s.id, [c.id for c in classes])
    return total
