# Curriculum structure — what Fairview actually runs

The authoritative record of the school's real structure, as read off Educare.
Written because nine screenshots in October 2026 showed how much of what we had
modelled was invented; anything here that is a *reading* of Educare says where
it was read, and anything that is still a *statement* says so.

## Sections, years and the subject catalogue

Three sections, with **separate subject catalogues** behind Educare's "Select
School of Subject" picker — 9 Early Years + 21 Primary + 49 Secondary = **79
section-scoped subjects** (migrations 137 + 138). Four titles appear in more than
one catalogue (Mathematics in all three; Geography, Music and Humanities in two),
which is why a flat table could not hold them.

Year groups run **Year 1 – Year 12**, not the Nigerian JSS/SSS naming. Secondary
is Years 7–12. Departments are Educare's real three — Science, Language, Art and
Business — and 23 of the 49 Secondary subjects are deliberately unassigned, which
Educare itself shows as N/A. Early Years and Primary subjects carry no department
on purpose.

## The lower-school science progression — VERIFIED, all six years

**Source: Educare → Assign to Classes, pages for Years 7–12, checked 4 October
2026.**

| Years | Science subjects taken |
|---|---|
| 7, 8, 9 | `L S Biology`, `LS Chemistry`, `LS Physics` (grouped "LS Science") |
| 10, 11, 12 | the standalone `Biology`, `Chemistry`, `Physics` |

Educare does **not** model a subject that splits at a year boundary. It carries
two parallel sets and assigns whichever one a year takes — so "which years take
which set" is the recorded fact, and the two sets are distinct subjects.

This was previously the school's verbal statement rather than a reading, and was
marked UNVERIFIED in `scripts/load_subject_groups.py` when those rows were
loaded (commit `abbfba1`). It has now been read off Educare year by year, and
**the rows as loaded were correct**.

> Where it was verified matters: the subject-group **column** on the subject list
> shows only *that* a group exists, never which years take it. **Assign to
> Classes** is the page carrying the per-year assignment — which is why the
> boundary could not be confirmed from the earlier screenshots.

## Every Secondary year has its own subject list

Also from Assign to Classes, 4 October 2026:

- Educare assigns a **different full subject list to every Secondary year** — not
  one list per level, and not a single junior plus a single senior list. There is
  a large shared core, but each of the six years adds or drops subjects relative
  to its neighbours.
- **`JAMB / WAEC Practice` is taken by Year 12 only.**
- Year 12 also **drops** subjects its neighbouring senior years keep.

**These per-year lists are not recorded anywhere in the system yet**, and this
document deliberately does not reproduce them: the screenshots they came from
were in places only partly scrolled, so the lists are *probably* complete rather
than certainly so. Recording them is planned work with its own verification step.

## What `subject_groups` does and does not hold

13 rows, no migration (`scripts/load_subject_groups.py`):

- **6 rows, one per year** — the science progression above.
- **7 rows with `year_group = NULL`** — Basic Science, Pre-Vocational Studies,
  National Value Education, Cultural, Nigerian Language, Religion, Trade Subject.
  NULL means "not year-scoped", **not** "unknown"; no year range is invented for
  them, because Educare shows none.

It does **not** hold a year's full subject list and was never meant to.

> **NOTHING CONSUMES `subject_groups`.** The timetable router has CRUD for it; no
> report, enrolment path or mark-entry gate reads it. These rows **record** the
> curriculum, they do not **enforce** it. Making them load-bearing — gating which
> subjects a Year 8 class can be marked in — is a separate decision with its own
> blast radius, and is explicitly on hold.

## Known gaps

- Primary `Non-Verbal Skills` → `Reasoning` department is still **UNVERIFIED**
  against Educare (`scripts/build_primary_subjects.py`). Unrelated to the
  Secondary year boundary resolved above.
- Educare's Primary list has no `Home Maker`; ours was a misreading of the
  abbreviated `Hm` column header (= Humanities) and was renamed rather than
  duplicated, so its 180 enrolments and 12 timetable rows moved with it.
- Early Years carries no subject rows by design.

See also `PERMISSION_MATRIX.md` for the gates that read class/section structure.
