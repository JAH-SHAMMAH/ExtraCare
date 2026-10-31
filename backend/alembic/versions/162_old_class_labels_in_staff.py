"""Replace old class names (SS2, JSS1, Primary 3 ...) typed into staff labels

Revision ID: 162_old_class_labels_in_staff
Revises: 161_attendance_event_enum_names

Migration 042/154 renamed the class rows themselves, but free text typed into
staff records (department, names, the qualification / other-names held in
``users.preferences``) and role names still carried the old scheme, e.g.
"SS2 Class Teacher". Idempotent, data-only: only whole-word old labels change.
"""
import json
import re

import sqlalchemy as sa
from alembic import op

revision = "162_old_class_labels_in_staff"
down_revision = "161_attendance_event_enum_names"
branch_labels = None
depends_on = None

_SENIOR = {"1": "Year 10", "2": "Year 11", "3": "Year 12"}
_JUNIOR = {"1": "Year 7", "2": "Year 8", "3": "Year 9"}
_RULES = [
    (re.compile(r"\bJSS\s?([123])\b", re.I), lambda m: _JUNIOR[m.group(1)]),
    (re.compile(r"\bSSS?\s?([123])\b", re.I), lambda m: _SENIOR[m.group(1)]),
    (re.compile(r"\bPrimary\s?([1-6])\b", re.I), lambda m: f"Year {m.group(1)}"),
    (re.compile(r"\bNursery\s?1\b", re.I), lambda m: "Nursery"),
    (re.compile(r"\bNursery\s?2\b", re.I), lambda m: "Reception"),
]


def relabel(text):
    if not isinstance(text, str):
        return text
    for rx, fn in _RULES:
        text = rx.sub(fn, text)
    return text


def _walk(v):
    if isinstance(v, str):
        return relabel(v)
    if isinstance(v, list):
        return [_walk(x) for x in v]
    if isinstance(v, dict):
        return {k: _walk(x) for k, x in v.items()}
    return v


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "users" in tables:
        cols = {c["name"] for c in insp.get_columns("users")}
        want = [c for c in ("full_name", "department", "preferences") if c in cols]
        rows = bind.execute(sa.text(f"SELECT id, {', '.join(want)} FROM users")).mappings().all()
        for r in rows:
            sets, params = [], {"id": r["id"]}
            for c in want:
                old = r[c]
                if c == "preferences":
                    if isinstance(old, str):
                        try:
                            old = json.loads(old)
                        except ValueError:
                            continue
                    new = _walk(old)
                    if new != old and old is not None:
                        sets.append("preferences = :preferences")
                        params["preferences"] = json.dumps(new)
                else:
                    new = relabel(old)
                    if new != old:
                        sets.append(f"{c} = :{c}")
                        params[c] = new
            if sets:
                stmt = "UPDATE users SET " + ", ".join(sets) + " WHERE id = :id"
                if "preferences = :preferences" in sets and bind.dialect.name == "postgresql":
                    stmt = stmt.replace("preferences = :preferences", "preferences = CAST(:preferences AS JSON)")
                bind.execute(sa.text(stmt), params)
    if "roles" in tables:
        for rid, name in bind.execute(sa.text("SELECT id, name FROM roles")).all():
            new = relabel(name)
            if new != name:
                try:
                    with bind.begin_nested():  # unique (org, name) clash: leave that role alone
                        bind.execute(sa.text("UPDATE roles SET name = :n WHERE id = :i"), {"n": new, "i": rid})
                except Exception:  # noqa: BLE001
                    pass


def downgrade() -> None:
    pass  # a label change; intentionally not reversed
