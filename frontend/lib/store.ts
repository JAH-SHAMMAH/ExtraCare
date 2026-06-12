import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { AuthUser, Organization } from "@/types";
import { clearAuth } from "./api";
import { permissionAllowedForOrg } from "./workspace";

// ── Auth Store ────────────────────────────────────────────────────────────────

/** Phase 6.3 — view-layer role a user has selected to browse in. Drives the
 * sidebar filter + branched home page. Distinct from `user.roles` (what the
 * user CAN be) vs `activeRole` (what they're acting as right now). */
export type ActiveRole = "admin" | "teacher" | "parent" | "student";

interface AuthState {
  user: AuthUser | null;
  org: Organization | null;
  isAuthenticated: boolean;
  /** Null until /me/contexts resolves — layout renders a splash meanwhile. */
  activeRole: ActiveRole | null;
  setUser: (user: AuthUser) => void;
  setOrg: (org: Organization) => void;
  setActiveRole: (role: ActiveRole) => void;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      org: null,
      isAuthenticated: false,
      activeRole: null,

      setUser: (user) => set({ user, isAuthenticated: true }),
      setOrg: (org) => set({ org }),
      setActiveRole: (role) => set({ activeRole: role }),

      logout: () => {
        clearAuth();
        set({ user: null, org: null, isAuthenticated: false, activeRole: null });
      },

      hasPermission: (permission: string) => {
        const user = get().user;
        const org = get().org;
        if (!user) return false;
        if (user.primary_role === "super_admin") return true;
        if (!permissionAllowedForOrg(org, permission)) return false;
        if (user.permissions.includes("*")) return true;
        if (user.permissions.includes(permission)) return true;
        const namespace = permission.split(":")[0];
        return user.permissions.includes(`${namespace}:*`);
      },
    }),
    {
      name: "extracare-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        org: state.org,
        isAuthenticated: state.isAuthenticated,
        activeRole: state.activeRole,
      }),
    }
  )
);

// ── UI Store ──────────────────────────────────────────────────────────────────

interface UIState {
  sidebarOpen: boolean;
  activeModule: string;
  setSidebarOpen: (open: boolean) => void;
  setActiveModule: (module: string) => void;
  toggleSidebar: () => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  activeModule: "dashboard",
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setActiveModule: (module) => set({ activeModule: module }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
