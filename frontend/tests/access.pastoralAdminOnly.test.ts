import { describe, it, expect } from "vitest";
import { canAccessPath } from "@/lib/access";

const teacher = (p: string) =>
  ["school:behaviour:read", "school:behaviour:write", "school:pastoral:read", "school:journals:write"].includes(p);
const admin = () => true;
const base = "/dashboard/modules/school/";

describe("pastoral is admin-only except Pastoral Discipline", () => {
  for (const r of ["pastoral-dashboard", "pastoral-students", "pastoral-report", "point-entry"]) {
    it(`teacher blocked from ${r}`, () => {
      expect(canAccessPath(base + r, teacher)).toBe(false);
      expect(canAccessPath(base + r, admin)).toBe(true);
    });
  }
  it("teacher keeps Pastoral Discipline", () => {
    expect(canAccessPath(base + "behaviour-sanction", teacher)).toBe(true);
  });
});

describe("subjects module access", () => {
  it("Student Enrolment is admin-only; Class List stays open to teachers", () => {
    expect(canAccessPath(base + "student-enrolment", teacher)).toBe(false);
    expect(canAccessPath(base + "student-enrolment", admin)).toBe(true);
    expect(canAccessPath(base + "class-list", (p) => p === "school:students:read")).toBe(true);
  });
});
