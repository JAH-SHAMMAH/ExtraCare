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

**These per-year lists are not recorded anywhere in the system**, and nothing
enforces them. They are set out below so the structure is written down even
though no table holds it.

### The six lists — CONFIRMED

**Source: Educare → Assign to Classes, the "Subjects in Level" column read
top-to-bottom for each of Years 7–12, 4 October 2026.**

Names below are **our** spellings. Ours transcribe Educare's own misspellings
faithfully, so three differ from how they are usually written:
`REHAERSAL` (Rehearsal), `Skill Aquisition` (Skill Acquisition), and
`Fashion Design And Garment Making` (shown abbreviated in places as
"Fashion Design").

**Shared by all six years — 11 subjects:** Agricultural science, C. R. S.,
Civic education, Digital Technology, English studies, French, I. R. S.,
Intervention Class, Mathematics, REHAERSAL, Reading Time.

**Years 7–9 — the junior list (27 subjects).** Years 8 and 9 are *identical*;
Year 7 adds three.

> English studies, Mathematics, **L S Biology, LS Chemistry, LS Physics**,
> Basic Technology, Business studies, Agricultural science, Digital Technology,
> Social studies, Civic education, Music, Cultural and creative arts,
> Home economics, Hausa, Igbo, Yoruba, C. R. S., French, PHE, I. R. S.,
> Security Education, IXL Math Prep, History, Reading Time, REHAERSAL,
> Intervention Class
>
> **Year 7 also (30):** Fashion Design And Garment Making, Livestock Farming,
> Social And Citizenship Studies

**Years 10–12 — the senior list (26 subjects shared).**

> English studies, Mathematics, Agricultural science, Digital Technology,
> Civic education, C. R. S., French, I. R. S., **Biology, Chemistry, Physics**,
> Economics, Marketing, Government, Geography, Accounting, Further mathematics,
> Technical drawing, Catering and Craft practice, Visual Arts,
> Literature in English, Commerce, Reading Time, REHAERSAL, Intervention Class,
> Skill Aquisition
>
> **Year 10 also (30):** Sociology, Fashion Design And Garment Making,
> Livestock Farming, Citizenship And Heritage Studies
> **Year 11 also (27):** IXL Math Prep
> **Year 12 also (28):** IXL Math Prep, JAMB / WAEC Practice

| Year | Subjects | Unique to that year |
|---|---|---|
| 7 | 30 | Social And Citizenship Studies |
| 8 | 27 | — |
| 9 | 27 | — |
| 10 | 30 | Sociology, Citizenship And Heritage Studies |
| 11 | 27 | — |
| 12 | 28 | JAMB / WAEC Practice |

Two things that are easy to get backwards:

- **History, PHE and Security Education are Years 7–9 only.** They leave at the
  Year 9 → 10 boundary, not at 11 → 12.
- **Year 12 drops nothing.** It is exactly Year 11 plus `JAMB / WAEC Practice`.

`Computer Hardware And GSM Repairs` is in the catalogue but **assigned to no
year** — unassigned in all six. That is correct, not a gap.

### What the data says against those lists

Read-only dry run against production, 4 October 2026
(`scripts/dry_per_year_subjects.py`):

- All **48** listed names resolve to our Secondary catalogue; **12 of 12**
  Secondary classes place into a year.
- **Years 10, 11 and 12 are clean** — nothing outside their lists.
- **Years 7, 8 and 9 (six classes) carry six subjects Educare does not assign
  to them:** Biology, Chemistry, Physics, Economics, Geography, Government.
  That is **1,619 marks, 540 enrolments and 60 timetable rows** outside the
  lists.

The science trio has an obvious junior counterpart (`L S Biology` /
`LS Chemistry` / `LS Physics`). **Economics, Geography and Government have
none** — Years 7–9 do not take them in any form.

> **ENFORCEMENT IS ON HOLD.** No gate reads these lists, no table holds them,
> and none is planned until the Years 7–9 data is reconciled or explicitly
> accepted as seed noise. A gate armed today would block mark entry for six
> real classes.

### The reconciliation decision — step 1 only

A second read-only diagnostic (`scripts/dry_reconcile_junior.py`) settled what
could safely be done. Two findings decided it:

- **All six junior classes have a PUBLISHED Autumn report; Spring is
  unpublished.** Re-pointing marks would therefore change a card a parent has
  already seen, and would do so for Autumn but not Spring — leaving the two
  terms describing different subjects for the same pupil.
- **The 60 timetable rows are 36 pairs plus 24 exact duplicates.** Year 7's two
  classes hold one row per pair (12); Years 8 and 9's four classes hold two
  identical rows each (4 × 6 = 24 pairs → 48 rows). 12 + 48 = 60. The duplicates
  are same class, subject, day *and* time — `timetables` has no unique
  constraint on that combination, which is how they got in.

**Decision (2026-10-04):**

| Step | Action | Status |
|---|---|---|
| 1 | Remove the 24 duplicate timetable rows, keeping the older `id` | **approved** |
| 2 | Re-point Biology/Chemistry/Physics → the LS subjects | **deferred** |
| 3 | Delete Economics/Geography/Government rows | **deferred** |

Steps 2 and 3 are deferred **because Autumn is published**: a partial re-point
would leave the Autumn and Spring cards inconsistent with each other. The LS
subjects hold no rows, so step 2 would not collide — it is deferred on the
published-report grounds alone, not on any technical obstacle.

Step 1 is independent of the curriculum question entirely: no mark, enrolment or
report reads `timetables`, so its blast radius is the timetable grid. It runs
dry-run by default behind an explicit apply flag, writes a manifest of the 24
deleted ids that is verified **by content** before the first change, and
restores through `--remove`.

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
