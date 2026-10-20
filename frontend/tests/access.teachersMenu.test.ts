import { describe, it, expect } from "vitest";
import { canAccessPath } from "@/lib/access";

const has = (...perms: string[]) => (p: string) => perms.includes(p);
const VIEW = "/dashboard/modules/school/teachers";
const ASSIGN = "/dashboard/modules/school/teachers/assign";
const BULK = "/dashboard/modules/school/teachers/bulk";

describe("Teachers menu access", () => {
  it("settings admin sees all three", () => {
    const h = has("settings:read", "settings:write");
    expect(canAccessPath(VIEW, h)).toBe(true);
    expect(canAccessPath(ASSIGN, h)).toBe(true);
    expect(canAccessPath(BULK, h)).toBe(true);
  });
  it("school head (school_admin:read, no settings scope) sees View Teachers only", () => {
    const h = has("school_admin:read", "school:read");
    expect(canAccessPath(VIEW, h)).toBe(true);
    expect(canAccessPath(ASSIGN, h)).toBe(false);
    expect(canAccessPath(BULK, h)).toBe(false);
  });
  it("HR manager sees View Teachers only", () => {
    const h = has("hr:write", "hr:read", "users:read");
    expect(canAccessPath(VIEW, h)).toBe(true);
    expect(canAccessPath(ASSIGN, h)).toBe(false);
  });
  it("a teacher sees none of it", () => {
    const h = has("school:classes:read", "school:teachers:read", "hr:read");
    expect(canAccessPath(VIEW, h)).toBe(false);
    expect(canAccessPath(ASSIGN, h)).toBe(false);
  });
});
