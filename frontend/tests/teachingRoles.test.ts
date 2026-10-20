import { describe, it, expect } from "vitest";
import { isTeachingRoleSlug } from "@/lib/teachingRoles";

describe("isTeachingRoleSlug", () => {
  it("flags teacher-tier roles", () => {
    for (const s of ["teacher", "Teacher", "head_teacher", "instructor"]) expect(isTeachingRoleSlug(s)).toBe(true);
  });
  it("does not flag admin / finance / HR roles", () => {
    for (const s of ["org_admin", "principal", "accountant", "hr_manager", "librarian", "", null, undefined]) expect(isTeachingRoleSlug(s as any)).toBe(false);
  });
});
