/**
 * One way to write a class's name for display.
 *
 * ~~~ WHAT WENT WRONG ~~~
 * The dashboard's School Class Distribution chart built its labels as
 * `${c.name} ${c.section}`, where `section` is the ARM (`school_classes.section`,
 * free text, placeholder "e.g. A") and not the school section. Fairview's Year
 * classes are already *named* "Year 1 A", so the chart printed "YEAR 1 A A" —
 * 24 of 31 classes. The remaining Early Years classes are named "Reception
 * Olive" and carry a synthetic arm, so they printed "RECEPTION OLIVE A", an arm
 * Educare's real names ("RECEPTION OLIVES", "YEAR 6 PEARL") do not have.
 *
 * Every other surface — 46 of them, from class lists to timetables to report
 * headers — already used the stored name verbatim. The chart was the outlier,
 * so this helper codifies what the rest of the app already did and gives the
 * three arm-consuming surfaces one place to agree.
 *
 * THE RULE: show the name exactly as stored; append the arm only when the name
 * does not already end in it. Casing is never changed — "as stored" and
 * "uppercased" are different instructions, and the chart's own `tickFormatter`
 * uppercase is what made "YEAR 1 A A" rather than "Year 1 A A".
 *
 * ~~~ WHAT THIS CANNOT FIX ~~~
 * For "Reception Olive" + arm "A" the name genuinely does not end in "A", so
 * the arm IS appended. No display rule can tell a redundant arm from a real one
 * when the name does not contain it. Those 6 rows are wrong DATA — Educare has
 * no A/B for Early Years — and clearing `section` on them belongs with the
 * rename, not here. The same applies after the rename: "YEAR 6 PEARL" + arm "A"
 * would gain an "A" too, so the rename has to clear `section` for all 31.
 */

export interface ClassLike {
  name?: string | null;
  /** The ARM (`school_classes.section`), e.g. "A" — not the school section. */
  section?: string | null;
}

/**
 * True when `name` already ends in `arm`, at a word boundary.
 *
 * Boundary-aware rather than a bare `endsWith`, in both directions:
 *   • "Year 1 A"  + "A" -> true  (space before it)
 *   • "Year 1A"   + "A" -> true  (digit before it; a plausible hand-typed form)
 *   • "Nursery Maples" + "S" -> FALSE, because the "s" is the tail of a word
 *     rather than an arm. A bare endsWith would have swallowed it.
 */
function alreadyEndsWithArm(name: string, arm: string): boolean {
  const n = name.toLowerCase();
  const a = arm.toLowerCase();
  if (n === a) return true;
  if (!n.endsWith(a)) return false;
  const before = name.charAt(name.length - arm.length - 1);
  return !/[a-z]/i.test(before);
}

export function classLabel(cls: ClassLike | null | undefined): string {
  const name = (cls?.name ?? "").trim();
  const arm = (cls?.section ?? "").trim();

  // An arm with no name is better than an empty label: it at least identifies
  // the row, and an empty axis tick looks like a rendering fault.
  if (!name) return arm;
  if (!arm) return name;
  return alreadyEndsWithArm(name, arm) ? name : `${name} ${arm}`;
}
