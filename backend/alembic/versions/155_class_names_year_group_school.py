"""year_groups.section_id (which school), backfill; classes renamed to Fairview's names

Revision ID: 155_class_names_school
Revises: 154_year_labels
"""
import re

import sqlalchemy as sa
from alembic import op

revision = "155_class_names_school"
down_revision = "154_year_labels"
branch_labels = None
depends_on = None

# Class names by year group, in stream order (A, B, C ...).
STREAMS = {
    "play group": ["Playgroup"],
    "pre-nursery": ["Lilac", "Lilies"],
    "nursery": ["Blossom", "Maples"],
    "reception": ["Olives", "Tulip"],
    "year 1": ["Amber", "Onyx"], "year 2": ["Ruby", "Beryl"], "year 3": ["Crystal", "Silver"],
    "year 4": ["Gold", "Topaz"], "year 5": ["Diamond", "Opal"], "year 6": ["Pearl"],
    "year 7": ["Coral", "Emerald"], "year 8": ["Garnet", "Sapphire"], "year 9": ["Aquamarine", "Peridot"],
    "year 10": ["Amethyst", "Jade", "Moonlight"],
    "year 11": ["Opaline", "Tanzanite", "Tourmaline"],
    "year 12": ["Alexandrite", "Morganite", "Taaffeite"],
}
_PREFIX = re.compile(r"^(play[\s-]?group|pre[\s-]?nursery|nursery|reception|year\s*\d{1,2})\s*[-]?\s*([A-D])$", re.I)


def _norm_group(raw: str) -> str:
    g = re.sub(r"\s+", " ", raw.strip().lower().replace("playgroup", "play group").replace("prenursery", "pre-nursery").replace("pre nursery", "pre-nursery"))
    return re.sub(r"^year(\d)", r"year \1", g)


def school_key(group_name: str) -> str | None:
    g = _norm_group(group_name)
    if g in ("play group", "pre-nursery", "nursery", "reception", "early years", "early-years"):
        return "early"
    m = re.match(r"^year (\d{1,2})$", g)
    if m:
        return "primary" if int(m.group(1)) <= 6 else "secondary"
    if any(k in g for k in ("alumni", "entrance", "interview", "employment")):
        return "secondary"
    return None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "section_id" not in {c["name"] for c in insp.get_columns("year_groups")}:
        op.add_column("year_groups", sa.Column("section_id", sa.String(36), nullable=True))
        op.create_index("ix_year_groups_section_id", "year_groups", ["section_id"])
        if bind.dialect.name != "sqlite":
            op.create_foreign_key("fk_year_groups_section", "year_groups", "school_sections", ["section_id"], ["id"], ondelete="SET NULL")

    # org -> {"early": id, "primary": id, "secondary": id}
    secs: dict[str, dict[str, str]] = {}
    for sid, org, name in bind.execute(sa.text("SELECT id, org_id, name FROM school_sections")).fetchall():
        n = (name or "").lower()
        key = "early" if "early" in n else "primary" if "primary" in n else "secondary" if "secondary" in n else None
        if key:
            secs.setdefault(org, {})[key] = sid

    # 1. year groups -> school
    group_school: dict[tuple[str, str], str] = {}
    for gid, org, name, cur in bind.execute(sa.text("SELECT id, org_id, name, section_id FROM year_groups")).fetchall():
        target = secs.get(org, {}).get(school_key(name or "") or "")
        if target:
            group_school[(org, _norm_group(name))] = target
            if not cur:
                bind.execute(sa.text("UPDATE year_groups SET section_id = :s WHERE id = :i"), {"s": target, "i": gid})

    # 2. classes: school, then Fairview's class names
    classes = bind.execute(sa.text("SELECT id, org_id, name, level, section_id FROM school_classes")).fetchall()
    taken = {(c[1], (c[2] or "").lower()) for c in classes}
    for cid, org, name, level, cur_sec in classes:
        group = _norm_group(level or "") if level else ""
        if not group:
            m0 = _PREFIX.match((name or "").strip())
            group = _norm_group(m0.group(1)) if m0 else ""
        target = group_school.get((org, group)) or secs.get(org, {}).get(school_key(group) or "")
        if target and not cur_sec:
            bind.execute(sa.text("UPDATE school_classes SET section_id = :s WHERE id = :i"), {"s": target, "i": cid})

        m = _PREFIX.match((name or "").strip())
        if not m:
            continue
        names = STREAMS.get(_norm_group(m.group(1)))
        idx = ord(m.group(2).upper()) - ord("A")
        if not names or idx >= len(names):
            continue
        suffix = names[idx]
        base = _norm_group(m.group(1))
        label = {"pre-nursery": "Pre-Nursery", "nursery": "Nursery", "reception": "Reception"}.get(
            base, "Year " + base.split()[1] if base.startswith("year") else "")
        new = suffix if base == "play group" else f"{label} {suffix}"
        if (org, new.lower()) in taken:
            continue
        taken.discard((org, (name or "").lower()))
        taken.add((org, new.lower()))
        bind.execute(sa.text("UPDATE school_classes SET name = :n, section = :s WHERE id = :i"),
                     {"n": new, "s": suffix, "i": cid})


def downgrade() -> None:
    pass  # label change; not reversed
