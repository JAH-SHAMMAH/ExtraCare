# Future features — scoped, not built

Features present in the Educare reference system (`fairview.educare.school`) that
have **no corresponding page or route** in this codebase. Each entry is a starting
point, not a specification — the behaviour described is inferred from the reference
UI and should be confirmed against it before building.

Nothing here is implemented. Items that *look* missing but are not:

| Looks missing | Actually |
|---|---|
| Reports Insight | Exists as the **Result Insight** tab inside Reports View |
| Transcript | Folded into **Mark Books & Transcripts** (`/mark-books`) |
| Approve Reports + Process Reports | One page here: **Approve / Process Reports** (`/report-workflow`) |
| Reports Upload | Built and wired (the note in `Sidebar.tsx` claiming otherwise is stale) |

---

## 1. Reports Award

Recognises top-performing pupils for a term — almost certainly "best in subject" and
"best overall" style awards that then surface on the report card or in a printable
awards list. Every input already exists: `report_card()` computes per-pupil
`position`, `average` and `subject_arm_average`, and `report_broadsheet()` already
ranks a whole class (`rows_out.sort(... reverse=True)` then assigns `position`), so
the selection logic is a query over data we already produce rather than new maths.

**Reuse:** the broadsheet ranking pass; `GradingBand` for award thresholds if awards
are grade-based; `ReportCardResponse` if awards print on the card.
**Open question:** are awards *stored* (an auditable record per term, needing a new
table) or *derived live* on each view? Derived is far cheaper and probably right.
**Complexity:** Low–Medium — low if derived, medium if it needs a persisted award
record with manual override.

## 2. Grade Analysis

A statistical breakdown of grade distribution — how many pupils fell in each band
(A*, A, B+ …) for a class / subject / term, presumably with a chart and pass-rate
percentages. Distinct from a broadsheet: the broadsheet lists pupils, this
aggregates them into bands.

**Reuse:** `_grade_for(pct, bands)` already maps a score to a band and is used by
both the broadsheet and the card, so counting per band is a grouping over existing
output. `ReportInsightTab` is the established chart pattern; the `dataviz` skill
covers chart conventions.
**Complexity:** Low — one endpoint returning band counts plus a chart. No schema.

## 3. Result Analysis

The reference sidebar lists **Result Analysis twice** in both Junior and Secondary
Report sections (see screenshots). Two entries with identical labels is most likely
either (a) a duplicate nav entry in the reference itself, or (b) two different
lenses — e.g. per-subject performance vs per-pupil progress. **Do not build from
this list alone — open both in the reference first and confirm what each shows.**
Likely overlaps heavily with Grade Analysis; they may be better as two tabs of one
page than two separate builds.

**Reuse:** same as Grade Analysis. If it is per-pupil-over-time, it also needs the
term axis — note `AcademicTerm` carries **no date range** (only `AcademicSession`
has `start_date`/`end_date`), which matters for any trend view.
**Complexity:** Unknown until the reference is checked — Low if it is a second lens
on the same aggregation, Medium if it is a cross-term trend.

## 4. Communication Book Intervention

A pastoral / behavioural log shared between school and parents — a running record of
notes home, concerns raised and follow-up actions. **Distinct from CBT's
"Intervention"**, which is exam remediation (`CBTIntervention`, `InterventionStatus`)
and must not be conflated with it despite the shared word.

**Reuse:** the Pastoral cluster already models the behavioural side
(`student_disciplinary_cases` — note this is the *student* table, distinct from HR's
`disciplinary_cases`), and the Feedback module already has a parent-visible
student-daily-report pattern worth copying for visibility rules. Parent visibility
should go through `ParentGuardian` + `_owned_student_ids()` / `_ensure_student_visible()`
rather than a new mechanism.
**Complexity:** Medium–High — the only one of the four needing a new table, a
migration, and parent-facing RBAC. Also the only one where getting visibility wrong
leaks one family's pastoral notes to another, so it needs the same
verify-as-the-real-role treatment the parent RBAC work got.

---

## Suggested order

1. **Grade Analysis** — smallest, no schema, proves the analysis pattern.
2. **Reports Award** — small if derived; reuses the ranking that already exists.
3. **Result Analysis** — only after confirming in the reference what it actually is.
4. **Communication Book Intervention** — largest, needs schema + parent RBAC.

---

## 5. Lost-update detection on Report Entry (optimistic locking)

**Status:** known behaviour, deliberately not fixed. Found by concurrency testing
2026-09-03 alongside two races that WERE fixed (`test_concurrency_races.py`).

When two teachers save the same `(student, subject, assessment)` cell at the same
time and a row already exists, **both succeed and the later write silently wins**.
No error, no warning, and the teacher whose value was discarded has no way to know.

This is not corruption — `uq_student_assessment_score` guarantees one row, and the
value stored is always some teacher's real entry. The concurrent-INSERT case is
separately handled: it recovers into an update rather than surfacing as a 500
(verified for 2, 3 and 5 simultaneous writers). What is missing is *detection* of
the overwrite.

**Why it was left:** a fix changes the contract rather than repairing a defect, and
needs a product decision about what a teacher sees when it happens.

**Options, roughly in order of cost:**

- **`updated_at` precondition.** The grid already loads scores; send the row's
  `updated_at` back with the save and reject with 409 if it moved. No migration —
  the column exists via `TimestampMixin`. Cheapest real fix.
- **Version column + optimistic locking.** `UPDATE ... WHERE version = :seen`,
  409 on a zero rowcount. Migration for the column; the sturdiest option, and the
  one to pick if score edits ever gain an audit trail.
- **Last-write-wins, made visible.** Keep the behaviour, record who overwrote whom
  in the audit log, and surface it in the UI after the fact. Cheapest of all,
  but the losing teacher still finds out late.

Whichever is chosen, the frontend needs a conflict path — a 409 with no UI for it
is worse than the silent overwrite, because the marks are lost AND the save appears
to fail for an unexplained reason.

**Reuse:** `StudentAssessmentScore.recorded_by` already records who wrote a value,
so "who overwrote whom" is derivable without new columns. `save_report_entry` in
`app/routers/modules/platform.py` is the single write path — there is no second
place to keep in sync.
