"""
Bootstrap parent/guardian login accounts for Fairview School.

Families are derived from the students already in the database: pupils sharing a
surname are grouped into sibling sets (capped at 3), so a parent's surname always
matches their children's. Family sizes follow a weighted pattern -- mostly 1-2
children, occasionally 3.

Each family gets ONE parent User (role=parent, force_password_change=True) linked
to its children through ParentGuardian.

Emails are on @fairviewschoolng.com because SINGLE_SCHOOL_MODE gates login to that
domain (app/config.py :: email_allowed) -- a parent on any other domain could not
sign in at all.

Idempotent: students who already have a guardian are skipped, and an email that
already exists is disambiguated with a numeric suffix.

Usage (dry-run):
    python -m scripts.bootstrap_parents "postgresql+asyncpg://user:pass@host/db?ssl=require"

Usage (write):
    python -m scripts.bootstrap_parents "postgresql+asyncpg://user:pass@host/db?ssl=require" --write
"""
from __future__ import annotations

import asyncio
import sys
import os

if len(sys.argv) < 2:
    print("usage: python -m scripts.bootstrap_parents <DATABASE_URL> [--write]")
    sys.exit(2)

os.environ['DATABASE_URL'] = sys.argv[1]

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.models.user import User, UserStatus
from app.models.role import Role
from app.models.modules.school import Student, ParentGuardian, SchoolClass
from app.core.security import hash_password, generate_secure_token

FAIRVIEW_ORG_ID = "0a6ee83d-7e2a-4089-914c-7c0ecafd4027"
EMAIL_DOMAIN = "fairviewschoolng.com"

# Realistic Nigerian given names, matching the style already used for staff
# (Igbo / Yoruba / Hausa mix). Picked deterministically from the surname so a
# re-run produces the same parent for the same family.
MALE_NAMES = [
    "Adebayo", "Chinedu", "Emeka", "Ibrahim", "Musa", "Tunde", "Yakubu",
    "Kunle", "Segun", "Obinna", "Uche", "Sani", "Aliyu", "Bashir", "Femi",
    "Dayo", "Nnamdi", "Ikechukwu", "Olumide", "Chukwuma", "Abubakar", "Gbenga",
]
FEMALE_NAMES = [
    "Amaka", "Ifeoma", "Blessing", "Grace", "Fatima", "Halima", "Adaeze",
    "Chiamaka", "Folake", "Aisha", "Zainab", "Nkechi", "Yetunde", "Chinyere",
    "Hauwa", "Titilayo", "Oluchi", "Kemi", "Ronke", "Amina", "Ijeoma", "Bukola",
]

# Weighted family-size cycle: 10 families -> 15 children (avg 1.5).
# Six 1-child, three 2-child, one 3-child.
FAMILY_SIZE_CYCLE = [1, 1, 2, 1, 2, 1, 1, 3, 2, 1]


def _stable_index(text: str, modulo: int) -> int:
    """Deterministic index from a string (not Python's salted hash())."""
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h % modulo


def _parent_name(surname: str, family_seq: int, taken_given: set[str]) -> str:
    """Pick a given name for this family's parent. Alternating gender by sequence,
    seeded from the surname so a re-run produces the same parent.

    ``taken_given`` holds lowercased given names already used by a PUPIL with this
    surname, or by an earlier parent of it -- skipped so no parent ends up sharing a
    full name with a real child (or with another parent of the same family name).
    """
    pool = FEMALE_NAMES if family_seq % 2 == 0 else MALE_NAMES
    start = _stable_index(f"{surname}{family_seq}", len(pool))
    for offset in range(len(pool)):
        given = pool[(start + offset) % len(pool)]
        if given.lower() not in taken_given:
            return f"{given} {surname}"
    # Exhausted this gender's pool for the surname -- cross over rather than
    # duplicate a pupil's name.
    other = MALE_NAMES if pool is FEMALE_NAMES else FEMALE_NAMES
    for offset in range(len(other)):
        given = other[(start + offset) % len(other)]
        if given.lower() not in taken_given:
            return f"{given} {surname}"
    return f"{pool[start]} {surname}"  # 44 names all taken: accept the clash


def _build_families(students: list[Student]) -> list[list[Student]]:
    """Group pupils into sibling sets by surname, capped by the size cycle."""
    by_surname: dict[str, list[Student]] = {}
    for s in students:
        by_surname.setdefault((s.last_name or "").strip(), []).append(s)

    families: list[list[Student]] = []
    cycle_pos = 0
    for surname in sorted(by_surname):
        siblings = sorted(by_surname[surname], key=lambda s: (s.first_name or "", s.student_id or ""))
        i = 0
        while i < len(siblings):
            size = FAMILY_SIZE_CYCLE[cycle_pos % len(FAMILY_SIZE_CYCLE)]
            cycle_pos += 1
            families.append(siblings[i:i + size])
            i += size
    return families


async def main() -> int:
    write_mode = "--write" in sys.argv
    db_url = sys.argv[1]

    clean_url = db_url.split("?")[0]
    engine = create_async_engine(clean_url, echo=False, connect_args={"ssl": "require"}, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        parent_role = (await db.execute(
            select(Role).where(Role.org_id == FAIRVIEW_ORG_ID, Role.slug == "parent")
        )).scalar_one_or_none()
        if not parent_role:
            print("ERROR: 'parent' role not found for this org.")
            print("Expected to exist from bootstrap_fairview_org.py / role sync.")
            await engine.dispose()
            return 1

        students = (await db.execute(
            select(Student).where(
                Student.org_id == FAIRVIEW_ORG_ID,
                Student.is_deleted == False,  # noqa: E712
            )
        )).scalars().all()

        class_names = {
            c.id: c.name for c in (await db.execute(
                select(SchoolClass).where(SchoolClass.org_id == FAIRVIEW_ORG_ID)
            )).scalars().all()
        }

        # Skip pupils who already have a guardian -- keeps this re-runnable.
        already_linked = set((await db.execute(
            select(ParentGuardian.student_id).where(ParentGuardian.org_id == FAIRVIEW_ORG_ID)
        )).scalars().all())

        eligible = [s for s in students if s.id not in already_linked]

        taken_emails = {
            (e or "").lower() for e in (await db.execute(select(User.email))).scalars().all()
        }

        print("=" * 78)
        print(f"{'WRITE' if write_mode else 'DRY-RUN'}: Parent accounts for Fairview School")
        print("=" * 78)
        print()
        print(f"Students (not deleted):        {len(students)}")
        print(f"Already have a guardian:       {len(already_linked)}")
        print(f"Eligible for a new parent:     {len(eligible)}")
        print()

        if not eligible:
            print("Nothing to do.")
            await engine.dispose()
            return 0

        families = _build_families(eligible)

        # Build the plan: one parent per family.
        # Given names already borne by a pupil of each surname -- a parent must not
        # share a full name with a real child. Built from ALL pupils, not just the
        # eligible ones, and grown as parents are named so two families with the
        # same surname never get the same parent either.
        used_given: dict[str, set[str]] = {}
        for s_ in students:
            used_given.setdefault((s_.last_name or "").strip().lower(), set()).add(
                (s_.first_name or "").strip().lower())
        # ...and by an existing USER of that surname: staff share the surname pool with
        # pupils, so without this a parent can be generated with a teacher's exact name
        # (the seeded teachers include Halima Suleiman and Grace Uzoma).
        for name in (await db.execute(
                select(User.full_name).where(User.org_id == FAIRVIEW_ORG_ID))).scalars().all():
            parts = (name or "").strip().split()
            if len(parts) >= 2:
                used_given.setdefault(parts[-1].lower(), set()).add(parts[0].lower())

        plan = []  # (parent_name, email, password, [students])
        for seq, kids in enumerate(families):
            surname = (kids[0].last_name or "").strip()
            taken = used_given.setdefault(surname.lower(), set())
            full_name = _parent_name(surname, seq, taken)
            taken.add(full_name.split()[0].lower())
            given = full_name.split()[0]
            local = f"{given}.{surname}".lower().replace(" ", "")
            email = f"{local}@{EMAIL_DOMAIN}"
            suffix = 2
            while email in taken_emails:
                email = f"{local}{suffix}@{EMAIL_DOMAIN}"
                suffix += 1
            taken_emails.add(email)
            plan.append((full_name, email, generate_secure_token(length=16), kids))

        sizes: dict[int, int] = {}
        for _n, _e, _p, kids in plan:
            sizes[len(kids)] = sizes.get(len(kids), 0) + 1

        print(f"Families to create:            {len(plan)}")
        for size in sorted(sizes):
            print(f"  {size} child{'ren' if size > 1 else '':<8}            {sizes[size]:4d} families")
        print(f"Children linked:               {sum(len(k) for _n, _e, _p, k in plan)}")
        print()

        print("-" * 78)
        print("SAMPLE MAPPING (first 12 families)")
        print("-" * 78)
        for full_name, email, _pw, kids in plan[:12]:
            print(f"  {full_name:<26} {email}")
            for k in kids:
                cls = class_names.get(k.class_id, "-")
                print(f"      -> {k.student_id:<10} {k.first_name} {k.last_name:<18} ({cls})")
        print()

        # Always surface the family containing our known test pupil.
        for full_name, email, pw, kids in plan:
            if any((k.student_id or "").upper() == "FSN-0031" for k in kids):
                print("-" * 78)
                print("TEST-PUPIL FAMILY (FSN-0031)")
                print("-" * 78)
                print(f"  parent : {full_name}")
                print(f"  email  : {email}")
                print(f"  pw     : {pw if write_mode else '(shown on --write)'}")
                for k in kids:
                    print(f"  child  : {k.student_id} {k.first_name} {k.last_name} ({class_names.get(k.class_id, '-')})")
                print()
                break

        # Collision audit -- proves the generated names are clean across ALL families,
        # not just the sample printed above. A parent must never share a full name
        # with a real pupil, with another parent, or with an existing user account.
        pupil_names = {f"{(s_.first_name or '').strip()} {(s_.last_name or '').strip()}".lower()
                       for s_ in students}
        existing_names = {(n or "").strip().lower() for n in (await db.execute(
            select(User.full_name).where(User.org_id == FAIRVIEW_ORG_ID))).scalars().all()}
        seen_parent: dict[str, int] = {}
        clash_pupil, clash_parent, clash_user, clash_email = [], [], [], []
        emails_seen: set[str] = set()
        for full_name, email, _pw, _kids in plan:
            key = full_name.lower()
            if key in pupil_names:
                clash_pupil.append(full_name)
            if key in existing_names:
                clash_user.append(full_name)
            if key in seen_parent:
                clash_parent.append(full_name)
            seen_parent[key] = seen_parent.get(key, 0) + 1
            if email.lower() in emails_seen or email.lower() in taken_emails - {email.lower()}:
                clash_email.append(email)
            emails_seen.add(email.lower())

        print("-" * 78)
        print("COLLISION AUDIT (all %d families)" % len(plan))
        print("-" * 78)
        print(f"  parent name == a pupil's name      : {len(clash_pupil)}")
        print(f"  parent name == another parent's    : {len(clash_parent)}")
        print(f"  parent name == an existing user    : {len(clash_user)}")
        print(f"  duplicate email in plan            : {len(clash_email)}")
        for label, rows in (("pupil", clash_pupil), ("parent", clash_parent),
                            ("user", clash_user), ("email", clash_email)):
            for r in rows[:10]:
                print(f"    !! {label}: {r}")
        if not (clash_pupil or clash_parent or clash_user or clash_email):
            print("  -> CLEAN: no collisions of any kind.")
        print()

        print("All accounts: role=parent, status=active, force_password_change=true")
        print()

        if not write_mode:
            print("=" * 78)
            print("DRY-RUN ONLY -- nothing written.")
            print(f'  python -m scripts.bootstrap_parents "{db_url}" --write')
            print("=" * 78)
            await engine.dispose()
            return 0

        print("Writing...")
        print()
        created = 0
        for full_name, email, pw, kids in plan:
            user = User(
                email=email.lower(),
                full_name=full_name,
                hashed_password=hash_password(pw),
                status=UserStatus.ACTIVE,
                org_id=FAIRVIEW_ORG_ID,
                force_password_change=True,
                email_verified=False,
            )
            user.roles = [parent_role]
            db.add(user)
            await db.flush()
            for idx, kid in enumerate(kids):
                db.add(ParentGuardian(
                    user_id=user.id,
                    student_id=kid.id,
                    relationship_type="parent",
                    is_primary=(idx == 0),
                    org_id=FAIRVIEW_ORG_ID,
                ))
            # Commit per family: the link to this database drops mid-run, and an
            # all-or-nothing transaction would discard every account created so
            # far. Re-running skips pupils that already have a guardian.
            await db.commit()
            created += 1
            if created <= 5 or created % 25 == 0:
                print(f"  {created:4d}/{len(plan)}  {full_name:<26} {email}  [committed]")

        print()
        print("=" * 78)
        print(f"Created {created} parent accounts, {sum(len(k) for _n, _e, _p, k in plan)} child links")
        print("=" * 78)
        print()
        print("LOGINS (save these -- passwords are not recoverable):")
        for full_name, email, pw, kids in plan:
            kid_ids = ", ".join((k.student_id or "?") for k in kids)
            print(f"  {email:<44} pw: {pw:<18} children: {kid_ids}")

        await engine.dispose()
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
