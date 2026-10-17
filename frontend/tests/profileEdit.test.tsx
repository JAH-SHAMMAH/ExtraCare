import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), usePathname: () => "/" }));
const update = vi.fn();
vi.mock("@/lib/api", () => ({ usersApi: { update: (...a: any[]) => update(...a) }, authApi: {} }));
const success = vi.fn();
vi.mock("sonner", () => ({ toast: { success: (m: string) => success(m), error: vi.fn() } }));

import { useAuthStore } from "@/lib/store";
import ProfilePage from "@/app/(dashboard)/dashboard/profile/page";

describe("profile edit", () => {
  beforeEach(() => {
    update.mockReset(); success.mockReset();
    useAuthStore.setState({ user: { id: "u1", email: "d@x.com", full_name: "Old Name", avatar_url: null, status: "active", org_id: "o", primary_role: "super_admin", permissions: ["*"], mfa_enabled: false } as any });
  });
  it("keeps permissions and says name changed", async () => {
    update.mockResolvedValue({ id: "u1", full_name: "New Name", phone: null, department: null, job_title: null, avatar_url: null });
    render(<QueryClientProvider client={new QueryClient()}><ProfilePage /></QueryClientProvider>);
    fireEvent.click(screen.getByText("Edit Profile"));
    fireEvent.change(screen.getByDisplayValue("Old Name"), { target: { value: "New Name" } });
    fireEvent.click(screen.getByText(/Save/));
    await waitFor(() => expect(success).toHaveBeenCalledWith("Name changed successfully."));
    expect(update).toHaveBeenCalledWith("u1", { full_name: "New Name" });
    expect(useAuthStore.getState().user?.permissions).toEqual(["*"]);
    expect(useAuthStore.getState().user?.primary_role).toBe("super_admin");
  });
});
