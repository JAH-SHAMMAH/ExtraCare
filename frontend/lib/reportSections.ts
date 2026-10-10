/**
 * Which report sections of the sidebar a section-scoped viewer may see.
 *
 * ~~~ WHAT THIS REPLACES ~~~
 * The sidebar matched a viewer's section to a report section by comparing NAMES
 * against three literals — `{ "Nursery": …, "Primary": …, "Secondary": … }`.
 * Fairview's EYFS section is named **"Early Years"**, so an Early Years teacher
 * matched nothing and the Nursery report section was hidden from the only people
 * who teach in it. Every page inside it answered her by URL; she simply could not
 * find one. Primary and Secondary worked only because their names happened to
 * equal the literals, so a rename in Report Setup would have hidden those too.
 *
 * The classification now arrives on the viewer's own section briefs as
 * `report_key`, resolved server-side by `services/report_sections.py` — it needs
 * the org's whole section list, because "junior" and "senior" are relative and a
 * single section cannot classify itself. Nothing on this path compares a name.
 *
 * ~~~ FAILING OPEN IS THE POINT ~~~
 * A viewer whose sections carry no usable `report_key` is NOT filtered: every
 * report section is shown. The fault being fixed is a lockout, and a resolution
 * gap must not reproduce it in a new shape. One report section too many is
 * noise; none is the bug. (It is also what keeps students safe here: `GET
 * /sections` is gated on `school:read`, which a student does not hold, so any
 * client-side resolution would have 403'd and hidden their report section
 * instead.)
 */

/** The report sections, in the order the sidebar lists them — senior first, as
 *  Educare does. Must stay in step with `REPORT_KEYS` in the Python module. */
export const REPORT_SECTION_KEYS = [
  "secondary-report",
  "junior-report",
  "nursery-report",
] as const;

export type ReportSectionKey = (typeof REPORT_SECTION_KEYS)[number];

export function isReportSectionKey(key: string | null | undefined): key is ReportSectionKey {
  return !!key && (REPORT_SECTION_KEYS as readonly string[]).includes(key);
}

/** A section brief as `/auth/me` and `/auth/login` return it. */
export interface ViewerSection {
  id: string;
  name?: string;
  report_key?: string | null;
}

/**
 * The report section keys this viewer may see, or `null` for "do not filter".
 *
 * `null` rather than an empty set on purpose: an empty set is a legitimate
 * answer meaning "nothing matches", and callers would hide everything. There is
 * no case here where hiding everything is right, so the unknown answer is given
 * a different shape that cannot be confused with it.
 */
export function visibleReportKeys(
  viewerSections: readonly ViewerSection[] | null | undefined,
): Set<ReportSectionKey> | null {
  const keys = (viewerSections ?? [])
    .map((s) => s?.report_key)
    .filter(isReportSectionKey);
  return keys.length ? new Set(keys) : null;
}

/**
 * Should a sidebar section with this key be shown?
 *
 * Anything that is not a report section is always shown — this function decides
 * report scoping only, and must never be the thing that hides Academics.
 */
export function reportSectionVisible(
  sectionKey: string,
  allowed: Set<ReportSectionKey> | null,
): boolean {
  if (!isReportSectionKey(sectionKey)) return true;
  if (allowed === null) return true;
  return allowed.has(sectionKey);
}
