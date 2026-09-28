#!/usr/bin/env python
"""Populate Spring Full-Term marks: Continuous Assessment and CBT Exam Score.

Writes `StudentAssessmentScore` rows only. It creates no CBT exam, no attempt and
no answer, and touches neither the CBT sync nor the legacy `grades` table — the
Exam mark lands directly in Spring's own "CBT Exam Score" assessment, which is
what the report engine reads.

WHAT THE ROWS LOOK LIKE. `source='entry'`, the same shape a Make Report save
produces, so nothing in the data or the UI marks these out as populated rather
than entered.

`recorded_by` names the DIRECTOR account, not the subject teacher. Either choice
reads as a real entry; this one puts the only name in the audit trail on the
account the school's owner controls, rather than attributing hundreds of marks to
teachers who did not enter them.

The rows are therefore indistinguishable from hand entry, which is the point and
also the risk, so reversal does not depend on being able to recognise them:

    every inserted row id is written to a MANIFEST outside the repository, and
    --remove deletes exactly the ids in that manifest and nothing else.

Keep the manifest. Without it these rows cannot be told apart from marks a person
actually entered, and removal would become guesswork.

SCOPE. Spring Full-Term only. Enrolled pupils only — a mark for a (pupil, subject)
with no `StudentSubjectEnrollment` row is refused by the API for good reason, and
this script honours the same rule rather than writing round it. A pupil is centred
on their own Autumn percentage in the same subject, so the spread looks like a
cohort rather than a random scatter, and the RNG is seeded so a re-run reproduces
it exactly.

    python scripts/populate_spring_marks.py <DSN>             # dry run
    python scripts/populate_spring_marks.py <DSN> --write
    python scripts/populate_spring_marks.py <DSN> --remove --write
"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import random
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

SEED = 20260928
# The account every row is attributed to. A real account, so the entry reads as a
# person's; the school's own, so no teacher carries a mark they did not enter.
RECORDED_BY_EMAIL = "director@fairviewschoolng.com"
SPREAD = 7.0                       # sd around the pupil's own Autumn level
TERM_NAME = "Spring"
REF_TERM = "Autumn"
SUB_TERM = ("Full-Term", "Full Term")
CA_NAME = "Continuous Assessment"
EXAM_NAME = "CBT Exam Score"

# Outside the repository and outside OneDrive. Deliberately NOT the session
# scratchpad: that is temporary, and this file is the only way back.
MANIFEST_DIR = pathlib.Path(r"C:\Users\SHAMMAH\fairview-backups")
MANIFEST = MANIFEST_DIR / "spring_marks_manifest.json"


def _resolve(argv) -> str:
    for a in argv[1:]:
        if not a.startswith("--"):
            return a.split("?")[0]
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env.split("?")[0]
    sys.exit("Pass the DSN as the first argument, or set DATABASE_URL.")


def _hist(vals: list[float], width: int, label: str) -> None:
    buckets: Counter = Counter()
    for v in vals:
        lo = int(v // width) * width
        buckets[lo] += 1
    print(f"   {label}")
    for lo in sorted(buckets):
        bar = "#" * max(1, buckets[lo] * 40 // max(1, len(vals)))
        print(f"      {lo:>3}-{lo + width - 1:<3} {bar} {buckets[lo]}")


async def main() -> int:
    write = "--write" in sys.argv
    remove = "--remove" in sys.argv
    url = _resolve(sys.argv)
    engine = create_async_engine(url, echo=False, connect_args={"ssl": "require"})
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from app.models.modules.academics import StudentSubjectEnrollment
    from app.models.modules.platform import (
        AcademicSubTerm, AcademicTerm, Assessment, GradingBand, GradingScale,
        StudentAssessmentScore,
    )
    from app.models.modules.school import SchoolClass, Student, Subject
    from app.models.user import User

    async with Session() as db:
        org = (await db.execute(select(Student.org_id).limit(1))).scalar_one()

        # ── --remove: exactly the manifest's ids ─────────────────────────────
        if remove:
            if not MANIFEST.exists():
                print(f"No manifest at {MANIFEST} — nothing to remove, and these rows "
                      f"cannot be identified without it.")
                return 1
            data = json.loads(MANIFEST.read_text())
            ids = data.get("row_ids", [])
            present = (await db.execute(
                select(StudentAssessmentScore.id).where(
                    StudentAssessmentScore.id.in_(ids))
            )).scalars().all()
            print(f"manifest written {data.get('written_at')}: {len(ids)} row id(s)")
            print(f"still present in the database: {len(present)}")
            if not write:
                print("\n(dry run — pass --write with --remove to delete)")
                return 0
            await db.execute(delete(StudentAssessmentScore).where(
                StudentAssessmentScore.id.in_(ids)))
            await db.commit()
            MANIFEST.rename(MANIFEST.with_suffix(
                f".removed-{datetime.now(timezone.utc):%Y%m%d%H%M%S}.json"))
            print(f"deleted {len(present)} row(s); manifest archived")
            return 0

        # ── the Spring assessments ───────────────────────────────────────────
        spring = (await db.execute(select(AcademicTerm).where(
            AcademicTerm.org_id == org, AcademicTerm.name == TERM_NAME))).scalars().first()
        ref = (await db.execute(select(AcademicTerm).where(
            AcademicTerm.org_id == org, AcademicTerm.name == REF_TERM))).scalars().first()
        sub = (await db.execute(select(AcademicSubTerm).where(
            AcademicSubTerm.org_id == org,
            AcademicSubTerm.name.in_(SUB_TERM)))).scalars().first()
        if not spring or not sub:
            print("Spring or Full-Term is not configured yet.")
            return 1
        targets = {a.name: a for a in (await db.execute(select(Assessment).where(
            Assessment.org_id == org, Assessment.term_id == spring.id,
            Assessment.sub_term_id == sub.id))).scalars().all()}
        missing = [n for n in (CA_NAME, EXAM_NAME) if n not in targets]
        if missing:
            print(f"Spring Full-Term is missing: {missing}. Configure the term first.")
            return 1
        for n, a in targets.items():
            print(f"target assessment: {n:24} max {a.max_score}  ({a.id})")

        # ── reference: each pupil's Autumn percentage per subject ────────────
        ref_pct: dict[tuple[str, str], float] = {}
        if ref is not None:
            for sid, subj, score, mx in (await db.execute(
                select(StudentAssessmentScore.student_id, StudentAssessmentScore.subject_id,
                       StudentAssessmentScore.score, Assessment.max_score)
                .join(Assessment, Assessment.id == StudentAssessmentScore.assessment_id)
                .where(Assessment.org_id == org, Assessment.term_id == ref.id)
            )).all():
                if score is not None and mx:
                    ref_pct[(sid, subj)] = float(score) / float(mx) * 100
        overall = (sum(ref_pct.values()) / len(ref_pct)) if ref_pct else 55.0

        # ── who is enrolled, and who teaches them ────────────────────────────
        enrolled = {(r[0], r[1]) for r in (await db.execute(
            select(StudentSubjectEnrollment.student_id,
                   StudentSubjectEnrollment.subject_id)
            .where(StudentSubjectEnrollment.org_id == org))).all()}
        pupils = {s.id: s for s in (await db.execute(select(Student).where(
            Student.org_id == org, Student.is_deleted == False))).scalars().all()}  # noqa: E712
        recorder = (await db.execute(select(User).where(
            User.org_id == org, User.email == RECORDED_BY_EMAIL))).scalars().first()
        if recorder is None:
            print(f"No account {RECORDED_BY_EMAIL!r} — refusing rather than writing "
                  f"marks with no author.")
            return 1
        subj_names = {s.id: s.name for s in (await db.execute(select(Subject).where(
            Subject.org_id == org))).scalars().all()}
        cls_names = {c.id: c.name for c in (await db.execute(select(SchoolClass).where(
            SchoolClass.org_id == org))).scalars().all()}

        existing = {(r[0], r[1], r[2]) for r in (await db.execute(
            select(StudentAssessmentScore.student_id, StudentAssessmentScore.subject_id,
                   StudentAssessmentScore.assessment_id)
            .where(StudentAssessmentScore.org_id == org,
                   StudentAssessmentScore.assessment_id.in_(
                       [a.id for a in targets.values()])))).all()}

        rng = random.Random(SEED)
        planned: list[dict] = []
        for (sid, subj) in sorted(enrolled):
            pupil = pupils.get(sid)
            if pupil is None or not pupil.class_id:
                continue
            base = ref_pct.get((sid, subj), overall)
            # One draw per pupil-subject, applied to both components, so CA and
            # Exam correlate the way a real pupil's marks do rather than being
            # independent noise.
            pct = max(0.0, min(100.0, rng.gauss(base, SPREAD)))
            wobble = rng.gauss(0, 4.0)
            for name, a in targets.items():
                if (sid, subj, a.id) in existing:
                    continue
                p = max(0.0, min(100.0, pct + (wobble if name == CA_NAME else -wobble)))
                planned.append({
                    "student_id": sid, "subject_id": subj, "assessment_id": a.id,
                    "assessment": name, "score": round(p / 100 * float(a.max_score), 2),
                    "max": float(a.max_score), "pct": p,
                    "recorded_by": recorder.id, "class_id": pupil.class_id,
                })

        print(f"\n== PLAN ==")
        print(f"   enrolled (pupil, subject) pairs : {len(enrolled)}")
        print(f"   rows to insert                  : {len(planned)}")
        print(f"   pupils                          : {len({p['student_id'] for p in planned})}")
        print(f"   subjects                        : {len({p['subject_id'] for p in planned})}")
        print(f"   classes                         : {len({p['class_id'] for p in planned})}")
        print(f"   source                          : 'entry'")
        print(f"   recorded_by                     : {recorder.email} "
              f"({recorder.full_name})")
        if not planned:
            print("\nNothing to do — every target row already exists.")
            return 0

        for name in (CA_NAME, EXAM_NAME):
            vals = [p["score"] for p in planned if p["assessment"] == name]
            if vals:
                print(f"\n   {name}: {len(vals)} rows, "
                      f"{min(vals)}..{max(vals)} of {planned[0]['max'] if name == CA_NAME else 100}, "
                      f"mean {sum(vals) / len(vals):.2f}")
                _hist([p["pct"] for p in planned if p["assessment"] == name], 10,
                      "as a percentage:")

        # ── resulting letter distribution, using the real bands ──────────────
        bands = [(b.grade, float(b.min_score)) for b in (await db.execute(
            select(GradingBand).join(GradingScale, GradingScale.id == GradingBand.scale_id)
            .where(GradingScale.org_id == org, GradingScale.scale_type == "numeric",
                   GradingScale.purpose == "grade"))).scalars().all()]

        def letter(pct: float) -> str:
            best = None
            for g, lo in bands:
                if pct >= lo and (best is None or lo > best[1]):
                    best = (g, lo)
            return best[0] if best else "?"

        by_pair: dict[tuple[str, str], dict[str, float]] = {}
        for p in planned:
            by_pair.setdefault((p["student_id"], p["subject_id"]), {})[p["assessment"]] = p["pct"]
        spring_letters: Counter = Counter()
        for pair, got in by_pair.items():
            ca_pct = got.get(CA_NAME, 0.0)
            ex_pct = got.get(EXAM_NAME, 0.0)
            total = ca_pct / 100 * 40 + ex_pct / 100 * 60      # CA(40) + Exam(60)
            spring_letters[letter(total)] += 1
        autumn_letters: Counter = Counter()
        for (sid, subj), pct in ref_pct.items():
            autumn_letters[letter(pct)] += 1

        print("\n== letter distribution: AUTUMN (actual) vs SPRING (planned) ==")
        order = [g for g, _ in sorted(bands, key=lambda x: -x[1])]
        print(f"   {'grade':6} {'autumn':>8} {'spring':>8}")
        for g in order:
            print(f"   {g:6} {autumn_letters.get(g, 0):>8} {spring_letters.get(g, 0):>8}")

        if not write:
            print(f"\n(dry run — nothing written. --write inserts and records the "
                  f"manifest at {MANIFEST})")
            return 0

        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        row_ids: list[str] = []
        for p in planned:
            rid = str(uuid.uuid4())
            row_ids.append(rid)
            db.add(StudentAssessmentScore(
                id=rid, student_id=p["student_id"], subject_id=p["subject_id"],
                assessment_id=p["assessment_id"], score=p["score"],
                recorded_by=p["recorded_by"], source="entry", org_id=org))
        # Manifest BEFORE the commit: a crash mid-write leaves a superset, which
        # --remove handles (it deletes what it finds). The reverse order could
        # leave rows with no record of them at all.
        MANIFEST.write_text(json.dumps({
            "written_at": datetime.now(timezone.utc).isoformat(),
            "term": TERM_NAME, "sub_term": sub.name,
            "assessments": {n: a.id for n, a in targets.items()},
            "row_ids": row_ids,
        }, indent=2))
        await db.commit()
        print(f"\ninserted {len(row_ids)} row(s); manifest at {MANIFEST}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
