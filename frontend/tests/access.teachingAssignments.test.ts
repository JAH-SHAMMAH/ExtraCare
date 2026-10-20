import { describe, it, expect } from "vitest";
import { canAccessPath } from "@/lib/access";
import { MODULE_SECTIONS } from "@/components/layout/Sidebar";

const has = (...p: string[]) => (x: string) => p.includes(x);
const PATH = "/dashboard/modules/school/teachers/assignments";

describe("Teaching Assignments", () => {
  it("is in the Teachers menu", () => {
    const t = MODULE_SECTIONS.find((s) => s.key === "teachers")!;
    expect(t.items.some((i) => i.href === PATH)).toBe(true);
  });
  it("is open to settings admins and the school head, not to teachers or HR", () => {
    expect(canAccessPath(PATH, has("settings:read"))).toBe(true);
    expect(canAccessPath(PATH, has("school_admin:read"))).toBe(true);
    expect(canAccessPath(PATH, has("school:classes:read", "school:teachers:read", "hr:read"))).toBe(false);
    expect(canAccessPath(PATH, has("hr:write"))).toBe(false);
  });
});
