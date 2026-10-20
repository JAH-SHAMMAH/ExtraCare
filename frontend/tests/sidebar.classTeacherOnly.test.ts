import { describe, it, expect } from "vitest";
import { MODULE_SECTIONS, navItemVisible } from "@/components/layout/Sidebar";

const REPORT_SECTIONS = ["secondary-report", "junior-report", "nursery-report"];
const teacherPerms = (p: string) => ["school:read", "school:write", "school:reports:write"].includes(p) || p.startsWith("school:reports");
const item = { href: "/dashboard/modules/school/reports-view", classTeacherOnly: true };

describe("Reports View / Result Analysis are class-teacher-only in every report section", () => {
  for (const key of REPORT_SECTIONS) {
    it(`${key} flags both items`, () => {
      const sec = MODULE_SECTIONS.find((s) => s.key === key)!;
      for (const href of ["reports-view", "result-analysis"]) {
        const it = sec.items.find((i) => i.href.endsWith(href))!;
        expect(it.classTeacherOnly, `${key}/${href}`).toBe(true);
      }
    });
  }
});

describe("navItemVisible with classTeacherOnly", () => {
  it("hides it from a teacher who leads no class", () => {
    expect(navItemVisible(item, "teacher", teacherPerms, { classTeacher: false, admin: false })).toBe(false);
  });
  it("shows it to a class teacher", () => {
    expect(navItemVisible(item, "teacher", teacherPerms, { classTeacher: true, admin: false })).toBe(true);
  });
  it("shows it to an administrator whether or not they lead a class", () => {
    expect(navItemVisible(item, "admin", () => true, { classTeacher: false, admin: true })).toBe(true);
  });
  it("does not lock out a class teacher whose saved session predates the flag", () => {
    expect(navItemVisible(item, "teacher", teacherPerms, { classTeacher: undefined, admin: false })).toBe(true);
  });
});
