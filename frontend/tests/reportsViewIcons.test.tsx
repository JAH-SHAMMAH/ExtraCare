import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

let bs: any;
vi.mock("@/hooks/useSchool", () => ({ useClasses: () => ({ data: [{ id: "c1", name: "Class A", level: "Year 5" }] }), useYearGroups: () => ({ data: [] }) }));
vi.mock("@/hooks/usePlatform", () => ({
  useTerms: () => ({ data: [{ id: "t1", name: "Autumn" }] }),
  useSubTerms: () => ({ data: [{ id: "s1", name: "Full-Term" }] }),
  useSessions: () => ({ data: [] }),
  useBroadsheet: () => ({ data: bs, isLoading: false, isError: false, error: null }),
  useReportCard: () => ({ data: { student_id: "p1", not_configured: true }, isLoading: false }),
  useReportCardsBulk: () => ({ data: [] }), useCommentGrid: () => ({}), useSaveComments: () => ({}),
}));
vi.mock("@/components/guards/PermissionGate", () => ({ useHasPermission: () => true }));
vi.mock("@/components/reports/ReportInsightTab", () => ({ ReportInsightTab: () => null }));

import ReportsViewPage from "@/app/(dashboard)/dashboard/modules/school/reports-view/page";

function open() {
  render(<ReportsViewPage />);
  const set = (label: string, v: string) => {
    const l = screen.getAllByText(label).find((e) => e.tagName === "LABEL")!;
    fireEvent.change(l.parentElement!.querySelector("select")!, { target: { value: v } });
  };
  set("Term", "t1"); set("Sub-Term", "s1"); set("Class", "c1");
  fireEvent.click(screen.getByRole("button", { name: /Process Result/ }));
}

describe("Reports View per-pupil icons", () => {
  it("Secondary/Junior: each name gets a view icon and an export icon that open that pupil", () => {
    bs = { report_key: "junior-report", subjects: [], bands: [], rows: [
      { student_id: "p1", student_name: "Ada Obi", subjects: {}, total: 0, average: 0, grade: null, position: 0 },
      { student_id: "p2", student_name: "Bayo Ade", subjects: {}, total: 0, average: 0, grade: null, position: 0 }] };
    open();
    expect(screen.getAllByLabelText(/View full report for/)).toHaveLength(2);
    expect(screen.getAllByLabelText(/Export PDF for/)).toHaveLength(2);
    fireEvent.click(screen.getByLabelText("View full report for Bayo Ade"));
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("Nursery has no marks but still lists pupils with the icons", () => {
    bs = { report_key: "nursery-report", not_configured: true, subjects: [], bands: [], rows: [
      { student_id: "p1", student_name: "Tiny Tim", subjects: {}, total: 0, average: 0, grade: null, position: 0 }] };
    open();
    expect(screen.getByText("Tiny Tim")).toBeTruthy();
    expect(screen.getByLabelText("Export PDF for Tiny Tim")).toBeTruthy();
    expect(screen.queryByText(/isn.t set up yet/)).toBeNull();
  });
});
