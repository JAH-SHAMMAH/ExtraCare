/** Role slugs on the teacher tier — these must belong to a school section.
 *  Mirror of TEACHING_ROLE_SLUGS in backend/app/services/teaching_roles.py. */
export const TEACHING_ROLE_SLUGS = [
  "teacher", "instructor", "head_teacher", "academic_coordinator",
  "head_of_department_secondary", "head_of_early_years", "homeroom_coordinator",
  "exam_subject_head", "spa_officer", "spa_manager",
] as const;

export function isTeachingRoleSlug(slug: string | null | undefined): boolean {
  return !!slug && (TEACHING_ROLE_SLUGS as readonly string[]).includes(slug.toLowerCase());
}
