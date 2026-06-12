import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock the api module so store import doesn't pull in axios
vi.mock("@/lib/api", () => ({
  clearAuth: vi.fn(),
}));

import { useAuthStore } from "@/lib/store";
import type { AuthUser, Organization } from "@/types";

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "u1",
    email: "user@example.com",
    full_name: "Test User",
    primary_role: "staff",
    permissions: [],
    org_id: "o1",
    ...overrides,
  } as AuthUser;
}

function makeOrg(overrides: Partial<Organization> = {}): Organization {
  return {
    id: "o1",
    name: "Business Org",
    slug: "business-org",
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

describe("useAuthStore.hasPermission", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, org: null, isAuthenticated: false });
  });

  it("returns false when no user is logged in", () => {
    expect(useAuthStore.getState().hasPermission("users:read")).toBe(false);
  });

  it("grants everything to super_admin", () => {
    useAuthStore.setState({ user: makeUser({ primary_role: "super_admin" }), isAuthenticated: true });
    expect(useAuthStore.getState().hasPermission("anything:write")).toBe(true);
  });

  it("grants everything when user has wildcard '*'", () => {
    useAuthStore.setState({ user: makeUser({ permissions: ["*"] }), isAuthenticated: true });
    expect(useAuthStore.getState().hasPermission("finance:delete")).toBe(true);
  });

  it("grants exact permission match", () => {
    useAuthStore.setState({ user: makeUser({ permissions: ["users:read"] }), isAuthenticated: true });
    expect(useAuthStore.getState().hasPermission("users:read")).toBe(true);
    expect(useAuthStore.getState().hasPermission("users:write")).toBe(false);
  });

  it("grants via namespace wildcard", () => {
    useAuthStore.setState({ user: makeUser({ permissions: ["payroll:*"] }), isAuthenticated: true });
    expect(useAuthStore.getState().hasPermission("payroll:write")).toBe(true);
    expect(useAuthStore.getState().hasPermission("payroll:read")).toBe(true);
    expect(useAuthStore.getState().hasPermission("finance:read")).toBe(false);
  });

  it("blocks cross-workspace permissions even if a stale role contains them", () => {
    useAuthStore.setState({
      user: makeUser({ permissions: ["business:read", "school:*"] }),
      org: makeOrg({ industry: "business", modules_enabled: ["business", "school"] }),
      isAuthenticated: true,
    });

    expect(useAuthStore.getState().hasPermission("business:read")).toBe(true);
    expect(useAuthStore.getState().hasPermission("school:read")).toBe(false);
  });
});
