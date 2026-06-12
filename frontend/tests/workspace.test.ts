import { describe, expect, it } from "vitest";
import {
  effectiveModulesForOrg,
  moduleAllowedForOrg,
  permissionAllowedForOrg,
  workspaceFor,
} from "@/lib/workspace";
import type { Organization } from "@/types";

function makeOrg(overrides: Partial<Organization>): Organization {
  return {
    id: "org-1",
    name: "Demo Org",
    slug: "demo",
    industry: "business",
    subscription_tier: "free",
    logo_url: null,
    primary_color: "#0057c2",
    modules_enabled: ["business"],
    max_users: 10,
    is_active: true,
    ...overrides,
  };
}

describe("workspace engine", () => {
  it("filters legacy school and hospital modules from a business tenant", () => {
    const org = makeOrg({
      industry: "business",
      modules_enabled: ["business", "school", "hospital", "crm", "inventory"],
    });

    expect(effectiveModulesForOrg(org)).toEqual(["business", "crm", "inventory"]);
    expect(moduleAllowedForOrg(org, "business")).toBe(true);
    expect(moduleAllowedForOrg(org, "school")).toBe(false);
    expect(moduleAllowedForOrg(org, "hospital")).toBe(false);
  });

  it("does not allow cross-workspace permission namespaces", () => {
    const business = makeOrg({ industry: "business", modules_enabled: ["business"] });
    const school = makeOrg({ industry: "school", modules_enabled: ["school"] });

    expect(permissionAllowedForOrg(business, "business:read")).toBe(true);
    expect(permissionAllowedForOrg(business, "school:read")).toBe(false);
    expect(permissionAllowedForOrg(school, "school:read")).toBe(true);
    expect(permissionAllowedForOrg(school, "crm:read")).toBe(false);
    expect(permissionAllowedForOrg(school, "users:read")).toBe(true);
  });

  it("returns a dedicated workspace definition for each industry", () => {
    expect(workspaceFor("school").primaryModule).toBe("school");
    expect(workspaceFor("business").primaryModule).toBe("business");
    expect(workspaceFor("hospital").primaryModule).toBe("hospital");
  });
});
