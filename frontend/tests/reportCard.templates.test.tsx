import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// The card imports data hooks for the print tabs; the Card view itself needs none.
vi.mock("@/hooks/useSchool", () => ({ useClasses: () => ({ data: [] }) }));
vi.mock("@/hooks/usePlatform", () => ({
  useTerms: () => ({ data: [] }), useSubTerms: () => ({ data: [] }), useBroadsheet: () => ({ data: null }),
  useReportCard: () => ({}), useReportCardsBulk: () => ({}), useCommentGrid: () => ({}), useSaveComments: () => ({}),
}));

import { Card } from "@/components/reports/ReportCardPrint";

const base = {
  student_name: "Ada Obi", class_name: "Year 5", term_name: "Autumn", position: 3, class_size: 20,
  columns: [{ key: "c1", name: "CA 1", max_score: 20 }], subjects: [
    { subject_id: "s1", subject_name: "Mathematics", values: { c1: 18 }, grade: "A", remark: "Excellent", subject_arm_average: 70 },
  ],
  bands: [], branding: {}, average: 80, total: 160,
};
const num = (v: any) => (v == null ? "–" : Number(v));

describe("report card templates", () => {
  it("junior card shows marks, behaviour and skills with the key", () => {
    render(<Card num={num} card={{ ...base, report_key: "junior-report", domain_blocks: [
      { domain_type: "affective", title: "AFFECTIVE DOMAIN", items: [{ domain_id: "a", name: "Punctuality", rating: "5" }], key: [{ label: "5", meaning: "Excellent" }] },
      { domain_type: "psychomotor", title: "PSYCHOMOTOR DOMAIN", items: [{ domain_id: "p", name: "Handwriting", rating: null }], key: [] },
    ] }} />);
    expect(screen.getByText("Mathematics")).toBeTruthy();
    expect(screen.getByText("AFFECTIVE DOMAIN")).toBeTruthy();
    expect(screen.getByText("Punctuality")).toBeTruthy();
    expect(screen.getByText(/5 = Excellent/)).toBeTruthy();
    expect(screen.getByText("Handwriting")).toBeTruthy();
    expect(screen.getByText("Position")).toBeTruthy();
  });

  it("nursery card prints areas and goals, with no marks table or position", () => {
    render(<Card num={num} card={{ ...base, report_key: "nursery-report", subjects: [], domain_blocks: [
      { domain_type: "eyfs_area", title: "Communication and Language", key: [{ label: "A", meaning: "Achieved" }, { label: "E", meaning: "Emerging" }],
        items: [{ domain_id: "g1", name: "Listening", rating: "A" }, { domain_id: "g2", name: "Speaking", rating: "E", comment: "Building sentences" }] },
    ] }} />);
    expect(screen.getByText("Communication and Language")).toBeTruthy();
    expect(screen.getByText("Building sentences")).toBeTruthy();
    expect(screen.queryByText("Mathematics")).toBeNull();
    expect(screen.queryByText("Student's Average")).toBeNull();
    expect(screen.queryByText("Position")).toBeNull();
  });

  it("nursery with no areas set up says so instead of printing an empty card", () => {
    render(<Card num={num} card={{ ...base, report_key: "nursery-report", subjects: [], domain_blocks: [] }} />);
    expect(screen.getByText(/No areas of learning have been set up/)).toBeTruthy();
  });

  it("unclassified section keeps the old marks layout", () => {
    render(<Card num={num} card={{ ...base, report_key: null }} />);
    expect(screen.getByText("Mathematics")).toBeTruthy();
    expect(screen.getByText("Position")).toBeTruthy();
  });
});
