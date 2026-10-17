import { renderToStaticMarkup } from "react-dom/server";
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

  it("secondary card has a Club/Sports Choice box listing the pupil's clubs; junior does not", () => {
    const blocks = [{ domain_type: "affective", title: "SKILLS AND BEHAVIOUR", items: [{ domain_id: "a", name: "Leadership", rating: "4" }], key: [] }];
    const { unmount } = render(<Card num={num} card={{ ...base, report_key: "secondary-report", clubs: ["Chess", "Football"], domain_blocks: blocks }} />);
    expect(screen.getByText("Club/Sports Choice")).toBeTruthy();
    expect(screen.getByText("Chess")).toBeTruthy();
    unmount();
    render(<Card num={num} card={{ ...base, report_key: "junior-report", clubs: ["Chess"], domain_blocks: blocks }} />);
    expect(screen.queryByText("Club/Sports Choice")).toBeNull();
  });

  it("nursery card prints areas and goals, with no marks table or position", () => {
    render(<Card num={num} card={{ ...base, report_key: "nursery-report", subjects: [], domain_blocks: [
      { domain_type: "eyfs_area", title: "Communication and Language", key: [{ label: "A", meaning: "Achieved" }, { label: "E", meaning: "Emerging" }],
        items: [{ domain_id: "g1", name: "Listening", rating: "A" }, { domain_id: "g2", name: "Speaking", rating: "E", comment: "Building sentences" }] },
    ] }} />);
    expect(screen.getByText("Communication and Language")).toBeTruthy();
    expect(screen.getByText("ELG 2")).toBeTruthy();
    expect(screen.getByText("ACHIEVEMENT")).toBeTruthy();
    expect(screen.getByText("Building sentences")).toBeTruthy();
    expect(screen.queryByText("Mathematics")).toBeNull();
    expect(screen.queryByText("Student's Average")).toBeNull();
    expect(screen.queryByText("Position")).toBeNull();
    expect(screen.queryByText("Times School Opened")).toBeNull();     // Nursery prints no attendance block
  });

  it("nursery card always has Learning Areas, ELG, Achievement and Sample Picture columns", () => {
    const mk = (photo: string | null) => ({ ...base, report_key: "nursery-report", subjects: [], domain_blocks: [
      { domain_type: "eyfs_area", title: "Literacy", key: [], items: [{ domain_id: "g", name: "Writing", rating: null, comment: "Writes her name", photo_url: photo }] }] });
    const { container, rerender } = render(<Card num={num} card={mk(null)} />);
    expect(screen.getByText("SAMPLE PICTURE")).toBeTruthy();      // present even with no picture
    expect(screen.getByText("Learning Areas")).toBeTruthy();
    expect(screen.getByText("ELG 1")).toBeTruthy();
    expect(screen.getByText("ACHIEVEMENT")).toBeTruthy();
    expect(container.querySelector('img:not([alt="School logo"]):not([aria-hidden])')).toBeNull();
    rerender(<Card num={num} card={mk("https://cdn.example/a.jpg")} />);
    expect(screen.getByText("SAMPLE PICTURE")).toBeTruthy();
    expect(container.querySelector('img[src="https://cdn.example/a.jpg"]')).toBeTruthy();
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

describe("report header", () => {
  it("shows the school logo top-left and a photo box top-right, even without a pupil photo", () => {
    const html = renderToStaticMarkup(<Card card={{ ...base, branding: { logo_url: "https://x/logo.png" }, report_key: "junior-report" }} num={(v: any) => v} />);
    expect(html).toContain('src="https://x/logo.png"');
    expect(html).toContain('data-testid="photo-placeholder"');
    const noLogo = renderToStaticMarkup(<Card card={{ ...base, branding: {}, report_key: "junior-report" }} num={(v: any) => v} />);
    expect(noLogo).toContain('src="/logo-square.png"');
    const withPhoto = renderToStaticMarkup(<Card card={{ ...base, photo_url: "https://x/ada.jpg", report_key: "junior-report" }} num={(v: any) => v} />);
    expect(withPhoto).toContain('src="https://x/ada.jpg"');
  });
});
