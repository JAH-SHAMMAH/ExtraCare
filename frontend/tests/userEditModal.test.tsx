import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const api = vi.hoisted(() => ({
  update: vi.fn().mockResolvedValue({}),
  setSections: vi.fn().mockResolvedValue({}),
  assignRoles: vi.fn().mockResolvedValue({}),
}));
vi.mock("@/lib/api", () => ({
  usersApi: api,
  schoolApi: { teachers: { get: vi.fn().mockResolvedValue({ section_ids: ["s1"] }) } },
}));
vi.mock("@/hooks/usePlatform", () => ({ useSections: () => ({ data: [{ id: "s1", name: "Primary" }, { id: "s2", name: "Secondary" }] }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { UserEditModal } from "@/components/users/UserEditModal";

const roles = [
  { id: "r-acct", name: "Accountant", slug: "accountant" },
  { id: "r-teacher", name: "Teacher", slug: "teacher" },
];
const user: any = { id: "u1", email: "a@x.com", full_name: "Ada Obi", phone: null, department: "Finance", job_title: "Bursar",
  roles: [{ id: "r-acct", name: "Accountant", slug: "accountant", color: "" }] };

const wrap = (ui: React.ReactElement) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

describe("UserEditModal", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the user's details and saves profile edits", async () => {
    const onClose = vi.fn();
    wrap(<UserEditModal user={user} availableRoles={roles} onClose={onClose} />);
    const name = screen.getByDisplayValue("Ada Obi") as HTMLInputElement;
    fireEvent.change(name, { target: { value: "Ada Okoye" } });
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => expect(api.update).toHaveBeenCalled());
    expect(api.update.mock.calls[0][1]).toMatchObject({ full_name: "Ada Okoye", department: "Finance", job_title: "Bursar" });
    expect(api.assignRoles).not.toHaveBeenCalled();     // roles untouched
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("makes a section required when a teaching role is ticked, and saves sections before roles", async () => {
    wrap(<UserEditModal user={user} availableRoles={roles} onClose={() => {}} />);
    fireEvent.click(screen.getByLabelText(/Teacher/));            // tick Teacher
    fireEvent.click(screen.getByText("Save changes"));
    expect(await screen.findByText(/at least one section/i)).toBeTruthy();
    expect(api.update).not.toHaveBeenCalled();

    fireEvent.click(screen.getByLabelText("Primary"));
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => expect(api.assignRoles).toHaveBeenCalled());
    expect(api.setSections).toHaveBeenCalledWith("u1", ["s1"]);
    expect(api.setSections.mock.invocationCallOrder[0]).toBeLessThan(api.assignRoles.mock.invocationCallOrder[0]);
  });

  it("renders nothing when closed and reports a server error without closing", async () => {
    const { container } = wrap(<UserEditModal user={null} availableRoles={roles} onClose={() => {}} />);
    expect(container.innerHTML).toBe("");
    const onClose = vi.fn();
    api.update.mockRejectedValueOnce({ response: { data: { detail: "You cannot manage an account with higher privileges than your own." } } });
    wrap(<UserEditModal user={user} availableRoles={roles} onClose={onClose} />);
    fireEvent.click(screen.getAllByText("Save changes")[0]);
    expect(await screen.findByText(/higher privileges/)).toBeTruthy();
    expect(onClose).not.toHaveBeenCalled();
  });
});
