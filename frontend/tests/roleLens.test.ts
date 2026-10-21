import { describe, it, expect } from "vitest";
import { lensForRole } from "@/lib/roleLens";

describe("lensForRole", () => {
  it("maps held roles to the dashboard home", () => {
    expect(lensForRole("Parent")).toBe("parent");
    expect(lensForRole("student")).toBe("student");
    expect(lensForRole("teacher")).toBe("teacher");
    expect(lensForRole("head_teacher")).toBe("teacher");
    expect(lensForRole("principal")).toBe("admin");
  });
  it("falls back to an available view", () => {
    expect(lensForRole("parent", ["teacher", "student"])).toBe("teacher");
    expect(lensForRole("teacher", ["teacher"])).toBe("teacher");
  });
});
