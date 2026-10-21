import type { ActiveRole } from "@/lib/store";

const TEACHING = new Set([
  "teacher", "instructor", "head_teacher", "academic_coordinator", "head_of_department_secondary",
  "head_of_early_years", "homeroom_coordinator", "exam_subject_head", "spa_officer", "spa_manager",
]);

/** Which dashboard home a held role should open. `available` is /me/contexts
 *  available_roles; when the natural pick isn't offered we fall back to the first
 *  one that is, so the dashboard never lands on a view the user can't have. */
export function lensForRole(slug: string | null | undefined, available: ActiveRole[] = []): ActiveRole | null {
  const s = (slug || "").toLowerCase();
  let want: ActiveRole = "admin";
  if (s === "parent") want = "parent";
  else if (s === "student") want = "student";
  else if (TEACHING.has(s)) want = "teacher";
  if (!available.length || available.includes(want)) return want;
  return available[0] ?? null;
}
