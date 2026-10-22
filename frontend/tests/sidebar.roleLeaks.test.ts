import { describe, it, expect } from "vitest";
import presets from "./fixtures_rolePresets.json";
import { CORE_NAV, MODULE_SECTIONS, navItemVisible } from "@/components/layout/Sidebar";

// hasPermission with the same scope hierarchy as the auth store.
const mk = (perms: string[]) => (p: string) => {
  if (perms.includes("*") || perms.includes(p)) return true;
  const a = p.split(":");
  if (perms.includes(a[0] + ":*")) return true;
  return a.length === 3 && perms.includes(a[0] + ":" + a[2]);
};
const P = presets as Record<string, string[]>;
function visible(role: string, lens: any, classTeacher = false): string[] {
  const h = mk(P[role]);
  const ctx = { staff: h("school:students:read"), student: lens === "student", teacher: lens === "teacher", admin: h("school_admin:write"), classTeacher };
  const items: any[] = [...CORE_NAV, ...MODULE_SECTIONS.flatMap((s) => s.items)];
  return items.filter((i) => navItemVisible(i, lens, h, ctx)).map((i) => i.href.split("?")[0]);
}

const STAFF_ONLY = [
  "/dashboard/hrm/leave", "/dashboard/hrm/my-info", "/dashboard/modules/school/make-report",
  "/dashboard/modules/school/students", "/dashboard/modules/school/teachers", "/dashboard/modules/school/fees",
  "/dashboard/modules/school/result-backup", "/dashboard/modules/school/feedback/daily-reports",
  "/dashboard/modules/school/feedback/student-daily-reports", "/dashboard/users", "/dashboard/settings/super",
];

describe("sidebar never offers staff pages to pupils or parents", () => {
  for (const [role, lens] of [["student", "student"], ["parent", "parent"]] as const) {
    it(role, () => {
      const v = visible(role, lens, true);
      for (const href of STAFF_ONLY) expect(v, `${role} sees ${href}`).not.toContain(href);
    });
  }
});

describe("teacher sidebar", () => {
  it("has no admin pages", () => {
    const v = visible("teacher", "teacher", false);
    for (const href of ["/dashboard/users", "/dashboard/modules/school/students", "/dashboard/modules/school/fees",
      "/dashboard/modules/school/teachers", "/dashboard/hrm/leave/admin", "/dashboard/modules/school/report-entry"])
      expect(v, href).not.toContain(href);
  });
  it("Result Backup is for class teachers only", () => {
    expect(visible("teacher", "teacher", false)).not.toContain("/dashboard/modules/school/result-backup");
    expect(visible("teacher", "teacher", true)).toContain("/dashboard/modules/school/result-backup");
  });
});
