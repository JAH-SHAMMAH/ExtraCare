// Helpers for the Make Report / Report Entry score grid.

export interface GridAssessment {
  id: string;
  name: string;
  max_score: number | string;
  sub_term_name?: string | null;
}

export interface SubTermDisplay {
  /** Label every column — the grid mixes sub-terms, so names alone are ambiguous. */
  perColumn: boolean;
  /** The single sub-term in play, to show once as a caption. Null when mixed or unknown. */
  only: string | null;
}

/**
 * Decide how to surface each assessment's sub-term.
 *
 * The grid is built from ALL of a term's assessments — the backend filters by
 * term and class level, never by sub-term — so a term carrying both a Half-Term
 * and a Full-Term "EXAM" yields two columns with identical headers and no way
 * to tell which is which. The API has always sent `sub_term_name`; the grid just
 * never rendered it.
 *
 * Labelling every column unconditionally would repeat "Full-Term" across five
 * headers in the common single-sub-term case, so:
 *   • mixed sub-terms  -> label each column, because that is the ambiguity
 *   • exactly one      -> say it once as a caption
 *   • none recorded    -> say nothing
 */
export function subTermDisplay(assessments: GridAssessment[] | undefined | null): SubTermDisplay {
  const names = Array.from(
    new Set((assessments ?? []).map((a) => a.sub_term_name).filter((n): n is string => !!n)),
  );
  if (names.length > 1) return { perColumn: true, only: null };
  return { perColumn: false, only: names[0] ?? null };
}

export interface TeachingAssignment {
  class_id: string;
  class_name?: string | null;
  subject_id: string;
  subject_name?: string | null;
}

export interface NamedRow {
  id: string;
  name?: string | null;
}

/**
 * The distinct classes a teacher has assignments for, in name order.
 *
 * Make Report used to offer one combined "class · subject" dropdown, which for a
 * teacher with 2 classes and 10 subjects meant 20 entries in a single list. The
 * split into Class + Subject turns that into 2 and 10.
 */
export function classesFromAssignments(assignments: TeachingAssignment[] | undefined | null): NamedRow[] {
  const seen = new Map<string, NamedRow>();
  for (const a of assignments ?? []) {
    if (!seen.has(a.class_id)) seen.set(a.class_id, { id: a.class_id, name: a.class_name ?? null });
  }
  return [...seen.values()].sort((x, y) => (x.name ?? "").localeCompare(y.name ?? ""));
}

/**
 * The subjects a teacher may enter marks for IN a given class.
 *
 * Dependent on purpose. The Timetable assigns per class per subject, so the two
 * fields are not independent: offering every subject against every class would
 * let a teacher pick a pair they do not teach, which the grid endpoint answers
 * with a 403. Fairview's timetable is currently dense — every teacher takes all
 * of their subjects in both their classes — so this narrows nothing today. It is
 * the sparse case it exists for.
 */
export function subjectsForClass(
  assignments: TeachingAssignment[] | undefined | null,
  classId: string,
): NamedRow[] {
  const seen = new Map<string, NamedRow>();
  for (const a of assignments ?? []) {
    if (a.class_id !== classId) continue;
    if (!seen.has(a.subject_id)) seen.set(a.subject_id, { id: a.subject_id, name: a.subject_name ?? null });
  }
  return [...seen.values()].sort((x, y) => (x.name ?? "").localeCompare(y.name ?? ""));
}

/**
 * The sub-term to select by default: "Full-Term" where it exists, else the first.
 *
 * Mirrors the backend's `_resolve_sub_term`, which prefers Full-Term for the same
 * reason — it is what nearly every assessment uses. Defaulting there means the
 * new selector shows the same columns the grid showed before it existed, so no
 * teacher's screen changes on the day this ships.
 */
export function defaultSubTermId(subTerms: NamedRow[] | undefined | null): string {
  const rows = subTerms ?? [];
  const full = rows.find((s) => {
    const n = (s.name ?? "").toLowerCase().replace(/[\s_]/g, "-");
    return n === "full-term";
  });
  return (full ?? rows[0])?.id ?? "";
}

/**
 * A mark as it should appear on a document a parent reads.
 *
 * Scores are stored as raw floats. A CBT percentage is a division, so it
 * arrives as 62.70341089190804, and rendering it unformatted put exactly that
 * on the parent report card. Two decimals is what the rest of the report
 * pipeline already rounds to, and trailing zeros are dropped so a clean mark
 * reads "70" rather than "70.00".
 *
 * Returns the em-dash the tables already use for a missing mark, so callers do
 * not each invent their own placeholder.
 */
export function formatMark(score: number | string | null | undefined): string {
  if (score === null || score === undefined || score === "") return "—";
  const n = typeof score === "number" ? score : Number(score);
  if (!Number.isFinite(n)) return "—";
  // parseFloat on the fixed string drops trailing zeros: 62.70 -> 62.7, 70.00 -> 70.
  return String(parseFloat(n.toFixed(2)));
}
