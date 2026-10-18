import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const save = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useParams: () => ({ module: "debtmemo" }) }));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/hooks/useOffice", () => ({
  useOfficeSchema: () => ({ isLoading: false, isError: false, data: { module: "debtmemo", label: "Debt Memo", can_write: true, resources: {
    memos: { debtor: { kind: "str", required: true }, amount: { kind: "float", required: true }, status: { kind: "choice:open|settled", required: false } },
    payments: { amount: { kind: "float", required: true } } } } }),
  useOfficeSummary: () => ({ data: { outstanding: 1500, memos: [{ id: "1", debtor: "Mr A", outstanding: 1500 }] } }),
  useOfficeRows: () => ({ isLoading: false, data: { items: [{ id: "1", debtor: "Mr A", amount: 1500, status: "open" }], total: 1 } }),
  useOfficeSave: () => ({ mutate: save, isPending: false }),
  useOfficeDelete: () => ({ mutate: vi.fn() }),
}));
import Page from "@/app/(dashboard)/dashboard/modules/office/[module]/page";

describe("Back-office module page", () => {
  it("shows the summary and records, and sends only filled fields on save", () => {
    render(<Page />);
    expect(screen.getAllByText("Mr A").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText(/Add Memo/));
    fireEvent.change(screen.getAllByRole("textbox")[1], { target: { value: "Mrs B" } });
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "300" } });
    fireEvent.submit(screen.getByText("Save").closest("form")!);
    expect(save.mock.calls[0][0].body).toEqual({ debtor: "Mrs B", amount: "300" });
  });
});
