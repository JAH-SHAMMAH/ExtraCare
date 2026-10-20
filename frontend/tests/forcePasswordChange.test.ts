import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/lib/store";

const user: any = { id: "u1", email: "a@b.com", full_name: "A", status: "active", org_id: "o", primary_role: "teacher", permissions: [], mfa_enabled: false, force_password_change: true };

describe("clearForcePasswordChange", () => {
  beforeEach(() => useAuthStore.setState({ user: null, isAuthenticated: false }));

  it("clears the stored flag so the layout stops redirecting to change-password", () => {
    useAuthStore.getState().setUser(user);
    expect(useAuthStore.getState().user?.force_password_change).toBe(true);
    useAuthStore.getState().clearForcePasswordChange();
    expect(useAuthStore.getState().user?.force_password_change).toBe(false);
    expect(useAuthStore.getState().user?.email).toBe("a@b.com");
  });
  it("is harmless when nobody is signed in", () => {
    useAuthStore.getState().clearForcePasswordChange();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
