import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { blockingFlag } from "@/lib/superFlags";

const save = vi.hoisted(() => vi.fn());
const user = vi.hoisted(() => ({ current: { primary_role: "org_admin", permissions: ["school:read"] } as any }));
vi.mock("@/lib/store", () => ({ useAuthStore: (sel: any) => sel({ user: user.current }) }));
vi.mock("@/hooks/useSuperSettings", () => ({
  useSuperSettings: () => ({ isLoading: false, data: {
    fields: [{ key: "wallet_manual_credit", tab: "School Settings", section: "Payments", label: "Toggle Wallet Manual Credit", kind: "bool", default: true }],
    values: { wallet_manual_credit: true } } }),
  useSaveSuperSettings: () => ({ mutate: save, isPending: false }),
  useSuperStruct: () => ({ data: { values: {
    student_dashboard: {}, teacher_dashboard: {}, doc_categories: [], notification_prefs: {}, role_perms: {},
    module_access: { teacher: [] },
    patterns: { email: { items: [{ type: "first_name", length: "full" }, { type: "surname", length: "full" }], separator: ".", suffix: "@x.com" } },
  }, meta: { student_dashboard_items: [], teacher_dashboard_items: [], notification_events: [], role_perm_items: [] } } }),
  useSaveSuperStruct: () => ({ mutate: save, isPending: false }),
}));
vi.mock("@/hooks/useUsers", () => ({ useAvailableRoles: () => ({ data: { items: [{ slug: "teacher", name: "Teacher" }] } }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
import Page from "@/app/(dashboard)/dashboard/settings/super/page";

describe("Super Settings", () => {
  it("is refused to anyone who is not the Super User", () => {
    render(<Page />);
    expect(screen.getByText("Super User only")).toBeTruthy();
  });
  it("lets the Super User flip a switch and save only what changed", () => {
    user.current = { primary_role: "super_user", permissions: ["*"] };
    render(<Page />);
    fireEvent.click(screen.getByRole("switch", { name: "Toggle Wallet Manual Credit" }));
    fireEvent.click(screen.getByText("Save Change"));
    expect(save.mock.calls[0][0]).toEqual({ wallet_manual_credit: false });
  });
});

describe("Super Settings structured tabs", () => {
  it("shows a live email example and saves the module tree as hidden pages", () => {
    user.current = { primary_role: "super_user", permissions: ["*"] };
    render(<Page />);
    fireEvent.click(screen.getByText("Email Pattern"));
    expect(screen.getByTestId("pattern-preview").textContent).toBe("chidiebere.ugwu@x.com");
    fireEvent.click(screen.getByText("Module Permissions Manager"));
    fireEvent.click(screen.getByRole("checkbox", { name: "Core Dashboard" }));
    fireEvent.click(screen.getByText("Update"));
    const call = save.mock.calls.at(-1)![0];
    expect(call.key).toBe("module_access");
    expect(call.value.teacher).toContain("/dashboard");
  });
});

describe("blockingFlag", () => {
  it("closes a page when its switch is off, opens it when on, and never blocks before flags load", () => {
    const p = "/dashboard/modules/school/biometric/devices";
    expect(blockingFlag(p, { school_biometric: false })?.flag).toBe("school_biometric");
    expect(blockingFlag(p, { school_biometric: true })).toBeNull();
    expect(blockingFlag(p, undefined)).toBeNull();
  });
  it("subject attendance is hidden until switched ON", () => {
    expect(blockingFlag("/dashboard/modules/school/timetable/subject-attendance", { subject_attendance: false })).not.toBeNull();
  });
  it("the store stays open to staff when closed to families", () => {
    const p = "/dashboard/modules/school/tuckshop";
    expect(blockingFlag(p, { open_store_for_parents: false }, { staff: true })).toBeNull();
    expect(blockingFlag(p, { open_store_for_parents: false }, { staff: false })).not.toBeNull();
  });
});
