import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), usePathname: () => "/" }));
vi.mock("@/components/guards/PermissionGate", () => ({ useHasPermission: () => true }));
const student = vi.hoisted(() => ({ id: "s1", student_id: "FSN-0001", first_name: "Chinedu", last_name: "Okoro", email: null, phone: null,
  date_of_birth: null, gender: "male", class_id: "c1", class_name: "Year 7 A", guardian_name: null, guardian_phone: null,
  address: null, avatar_url: "/uploads/x.png", is_active: true, created_at: "2026-01-01T00:00:00Z" }));
vi.mock("@/lib/api", () => ({
  schoolApi: {
    students: { list: vi.fn().mockResolvedValue({ items: [student], total: 474, page: 1, page_size: 25, total_pages: 1 }), get: vi.fn() },
    classes: { list: vi.fn().mockResolvedValue({ items: [{ id: "c1", name: "Year 7 A" }] }) },
    yearGroups: { list: vi.fn().mockResolvedValue([]) },
  },
  platformApi: { sections: { list: vi.fn().mockResolvedValue([]) } },
  uploadApi: {},
}));

import StudentsPage from "@/app/(dashboard)/dashboard/modules/school/students/page";

describe("students page", () => {
  it("shows class NAME (not id), photo, and profile/edit/remove actions", async () => {
    render(<QueryClientProvider client={new QueryClient()}><StudentsPage /></QueryClientProvider>);
    expect(await screen.findByText("Year 7 A", { selector: "span" })).toBeTruthy();
    expect(screen.getByAltText("Chinedu Okoro")).toBeTruthy();
    expect(screen.getByTitle("View full profile")).toBeTruthy();
    expect(screen.getByTitle("Edit profile")).toBeTruthy();
    expect(screen.getByTitle("Remove student")).toBeTruthy();
    expect(screen.getAllByText("474").length).toBeGreaterThan(0);
  });

  it("shows the school / year group / class / gender filters and the male and female counts", async () => {
    render(<QueryClientProvider client={new QueryClient()}><StudentsPage /></QueryClientProvider>);
    expect(await screen.findByText("Select School to View Students")).toBeTruthy();
    expect(screen.getByText("Select Year Group")).toBeTruthy();
    expect(screen.getByText(/No of Male\(s\)/)).toBeTruthy();
    expect(screen.getByText(/No of Female\(s\)/)).toBeTruthy();
  });

  it("shows a visible 'No photo yet' placeholder when a pupil has no photo", async () => {
    const { schoolApi } = await import("@/lib/api");
    (schoolApi.students.list as any).mockResolvedValueOnce({ items: [{ ...student, id: "s2", avatar_url: null }], total: 1, page: 1, page_size: 25, total_pages: 1 });
    render(<QueryClientProvider client={new QueryClient()}><StudentsPage /></QueryClientProvider>);
    expect((await screen.findAllByText("No photo yet")).length).toBeGreaterThan(0);
  });
});
