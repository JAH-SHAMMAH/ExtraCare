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
