import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const state = vi.hoisted(() => ({ card: null as any, error: null as any }));
vi.mock("@/hooks/useMyContexts", () => ({ useMyContexts: () => ({ isLoading: false, data: { as_parent: { children: [{ id: "c1", first_name: "Ada", last_name: "Obi", class_name: "Year 7 A" }] } } }) }));
vi.mock("@/hooks/usePlatform", () => ({
  useTerms: () => ({ data: [{ id: "t1", name: "Autumn", is_active: true }] }),
  useSubTerms: () => ({ data: [{ id: "s1", name: "Full-Term" }] }),
  useReportCard: () => ({ data: state.card, isLoading: false, error: state.error }),
}));
vi.mock("@/components/reports/ReportCardPrint", () => ({ Card: () => <div>NEW-STYLE-REPORT-CARD</div> }));

import ParentReportCardPage from "@/app/(dashboard)/dashboard/my-children/report-card/page";

describe("parent report card", () => {
  beforeEach(() => { state.card = null; state.error = null; });
  it("shows the designed report card (not the old table) when published", () => {
    state.card = { student_name: "Ada Obi" };
    render(<ParentReportCardPage />);
    expect(screen.getByText("NEW-STYLE-REPORT-CARD")).toBeTruthy();
    expect(screen.queryByText("Subject")).toBeNull();
  });
  it("explains when the report isn't published yet", () => {
    state.error = { response: { data: { detail: "This report has not been published yet. Please check back later." } } };
    render(<ParentReportCardPage />);
    expect(screen.getByText(/isn't published yet/)).toBeTruthy();
  });
});
