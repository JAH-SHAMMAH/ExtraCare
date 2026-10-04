import { describe, expect, it } from "vitest";
import { canAccessPath, permissionForPath } from "@/lib/access";

// My Leave was gated on `hr:read`, which two STAFF presets do not hold, so a
// cashier and a facilities user could not open their own leave page — while the
// API had always served them (POST, `?mine=true` and reading one's own row
// carry no permission check, and the router has no `dependencies=`).
//
// The presets below are transcribed from backend/app/models/role.py. They are
// deliberately tiny: that is the point — neither role holds anything in the
// `hr:*` family, so nothing short of opening the route reaches them.
const CASHIER = ["payments:read", "store:sell"];
const FACILITIES = [
  "school:read",
  "school_admin:facility:read",
  "school_admin:facility:write",
];
// An HR administrator, to prove the admin view did not come open in the process.
const HR_MANAGER = ["hr:read", "hr:write", "users:read", "users:write"];

/** Mirrors useAuthStore.hasPermission (incl. the broad→fine scope hierarchy). */
function checker(perms: string[]) {
  return (permission: string): boolean => {
    if (perms.includes(permission)) return true;
    const parts = permission.split(":");
    if (perms.includes(`${parts[0]}:*`)) return true;
    if (parts.length === 3 && perms.includes(`${parts[0]}:${parts[2]}`)) return true;
    return false;
  };
}

const MY_LEAVE = "/dashboard/hrm/leave";
const ENTITLEMENTS = "/dashboard/hrm/leave/entitlements";
const WHOLE_STAFF = "/dashboard/hrm/leave/admin";
const CONFIGURE = "/dashboard/hrm/leave/configure";
const ASSIGN = "/dashboard/hrm/leave/assign";

describe("My Leave is reachable by every authenticated role", () => {
  for (const [label, perms] of [
    ["cashier", CASHIER],
    ["facilities", FACILITIES],
  ] as const) {
    it(`${label} can open My Leave`, () => {
      expect(canAccessPath(MY_LEAVE, checker(perms))).toBe(true);
    });

    it(`${label} is not blocked by RouteGuard on a direct URL`, () => {
      // RouteGuard blocks on `required && !canAccessPath(...)`, so a non-null
      // requirement here would still stop the page even though canAccessPath
      // passes. Both halves have to agree or the fix only works in the sidebar.
      expect(permissionForPath(MY_LEAVE)).toBeNull();
    });

    it(`${label} can open their own entitlements (API 403s on anyone else's)`, () => {
      expect(canAccessPath(ENTITLEMENTS, checker(perms))).toBe(true);
    });
  }
});

describe("the whole-staff view stays gated", () => {
  for (const [label, perms] of [
    ["cashier", CASHIER],
    ["facilities", FACILITIES],
  ] as const) {
    it(`${label} still cannot open Leave Admin`, () => {
      expect(canAccessPath(WHOLE_STAFF, checker(perms))).toBe(false);
    });

    it(`${label} still cannot Configure or Assign leave`, () => {
      expect(canAccessPath(CONFIGURE, checker(perms))).toBe(false);
      expect(canAccessPath(ASSIGN, checker(perms))).toBe(false);
    });
  }

  it("Leave Admin still reports its requirement to RouteGuard", () => {
    // The longer prefix must keep winning. If opening /leave had captured
    // /leave/admin too, this would go null and the admin page would come open.
    expect(permissionForPath(WHOLE_STAFF)).toBe("hr:write");
  });

  it("an HR administrator still reaches all three admin pages", () => {
    const can = checker(HR_MANAGER);
    expect(canAccessPath(WHOLE_STAFF, can)).toBe(true);
    expect(canAccessPath(CONFIGURE, can)).toBe(true);
    expect(canAccessPath(ASSIGN, can)).toBe(true);
  });

  it("opening My Leave did not open the rest of HR", () => {
    // /dashboard/hrm → hr:write is the catch-all that made deleting the leave
    // entry impossible: without an explicit rule the route would have become
    // STRICTER, not open. Assert the catch-all still bites.
    const can = checker(CASHIER);
    expect(canAccessPath("/dashboard/hrm", can)).toBe(false);
    expect(canAccessPath("/dashboard/hrm/recruitment", can)).toBe(false);
    expect(canAccessPath("/dashboard/hrm/performance", can)).toBe(false);
    expect(canAccessPath("/dashboard/hrm/my-info", can)).toBe(false);
  });
});
