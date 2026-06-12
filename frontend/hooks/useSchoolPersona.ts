"use client";

import { useAuthStore } from "@/lib/store";

export type SchoolPersona = "admin" | "teacher" | "student";

/**
 * Derives the user's school-experience persona from auth state.
 *
 * Why this layer exists: the auth model has no first-class "student"/"teacher"
 * role — every user is an org member with a role like super_admin / org_admin /
 * staff / viewer. The school dashboards however expect a persona-shaped
 * experience. We map permissions to a persona so widgets stay declarative.
 *
 * Mapping:
 *   super_admin / org_admin / manager  → admin (school-wide oversight)
 *   any user with school:write         → teacher (incl. staff)
 *   read-only school members           → student (assumed; will surface
 *                                         "self" data when wired to identity)
 */
export function useSchoolPersona(): SchoolPersona {
  const { user, hasPermission } = useAuthStore();
  if (!user) return "student";

  if (
    user.primary_role === "super_admin" ||
    user.primary_role === "org_admin" ||
    user.primary_role === "manager"
  ) {
    return "admin";
  }

  if (hasPermission("school:write")) return "teacher";
  return "student";
}
