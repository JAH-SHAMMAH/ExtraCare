/**
 * What the School Class Distribution chart plots.
 *
 * Pulled out of the component so the selection rules can be tested directly:
 * the chart itself is a recharts `ResponsiveContainer`, which measures its
 * parent and renders nothing at zero size, so asserting on a render would test
 * the harness rather than the rule.
 *
 * ~~~ THE FAULT THESE RULES FIX ~~~
 * `currentData` filtered classes with `c.academic_year === currentSession`, an
 * equality. Fairview's Playgroup row holds a NULL `academic_year`, so it was
 * dropped from the chart entirely — 30 bars for 31 classes. It cost nothing
 * visible because Playgroup holds 0 pupils, so the headline total was still a
 * correct 450/450; but enrol one child there and they vanish from both the
 * chart and the count, with no empty state to explain where they went.
 */
import { yearGroupLabel, type ClassLike } from "./classLabel";

export interface DistributionClass extends ClassLike {
  academic_year?: string | null;
  student_count?: number | null;
  capacity?: number | null;
}

export interface DistributionRow {
  label: string;
  students: number;
  capacity?: number | null;
}

/**
 * The sessions named by these classes, newest first.
 *
 * Derived from `school_classes.academic_year`, which is what the rows carry —
 * NOT from `academic_sessions`. That is a real limitation and the reason the
 * "All sessions" view cannot be a time series; see `allSessionsRows`.
 */
export function sessionsOf(classes: readonly DistributionClass[]): string[] {
  return Array.from(
    new Set(classes.map((c) => c.academic_year).filter((y): y is string => !!y)),
  ).sort().reverse();
}

export function currentSessionOf(classes: readonly DistributionClass[]): string | null {
  return sessionsOf(classes)[0] ?? null;
}

/**
 * Does this class belong to the current session?
 *
 * TRUE WHEN IT NAMES NO SESSION AT ALL. A class row without an `academic_year`
 * is a class that exists on the roster now — the column is nullable and nothing
 * backfills it. Treating "unknown" as "not current" silently removes the class
 * and its pupils from the chart.
 *
 * With no resolvable session (every row NULL), everything is current: there is
 * no other session for a class to belong to, and an empty chart would be wrong.
 */
export function isInCurrentSession(
  cls: DistributionClass,
  currentSession: string | null,
): boolean {
  if (!cls.academic_year) return true;
  if (!currentSession) return true;
  return cls.academic_year === currentSession;
}

/**
 * One row per YEAR GROUP in the current session: arms ("Year 7 A", "Year 7 B")
 * are added together under "Year 7". Capacity is summed when every arm has one.
 */
export function currentSessionRows(
  classes: readonly DistributionClass[],
  currentSession: string | null = currentSessionOf(classes),
): DistributionRow[] {
  const groups = new Map<string, DistributionRow & { allCap: boolean }>();
  for (const c of classes.filter((x) => isInCurrentSession(x, currentSession))) {
    const label = yearGroupLabel(c);
    const key = label.toLowerCase();
    const g = groups.get(key) ?? { label, students: 0, capacity: 0, allCap: true };
    g.students += c.student_count ?? 0;
    if (typeof c.capacity === "number") g.capacity = (g.capacity ?? 0) + c.capacity;
    else g.allCap = false;
    groups.set(key, g);
  }
  return Array.from(groups.values())
    .map(({ label, students, capacity, allCap }) => ({ label, students, capacity: allCap ? capacity : null }))
    .sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
}

/**
 * The "All sessions" view — which is deliberately NOT a time series.
 *
 * It used to group classes by `academic_year`, producing one bar reading
 * "1 session on record" while two sessions existed, because 30 of 31 class rows
 * hold the same string. Grouping by `academic_sessions` instead would be WORSE:
 * `student_count` comes from `Student.class_id`, the CURRENT roster, so every
 * year's bar would show the same 450 pupils and look like real history.
 *
 * Students-per-class-per-session is what `student_class_history` will hold.
 * Until then this returns the current session alone and the UI says so.
 */
export function allSessionsRows(
  classes: readonly DistributionClass[],
  currentSession: string | null = currentSessionOf(classes),
): Array<DistributionRow & { classes: number }> {
  const rows = currentSessionRows(classes, currentSession);
  return [{
    label: currentSession ?? "Current session",
    students: rows.reduce((sum, r) => sum + r.students, 0),
    classes: classes.filter((c) => isInCurrentSession(c, currentSession)).length,
  }];
}
