import { describe, expect, it } from "vitest";

import {
  REPORT_SECTION_KEYS,
  isReportSectionKey,
  reportSectionVisible,
  visibleReportKeys,
  type ViewerSection,
} from "../lib/reportSections";

/**
 * The report-section scoping rule, and the lockout it replaces.
 *
 * THE BUG: the sidebar matched a viewer's section to a report section by NAME,
 * against the literal "Nursery". Fairview's EYFS section is named "Early Years",
 * so every Early Years teacher matched nothing and the Nursery report section
 * was hidden from her — while every page inside it answered her by URL.
 *
 * These tests are written so that reintroducing a name comparison fails them:
 * the briefs below carry names that do NOT match any report key, and the
 * expected result is driven entirely by `report_key`.
 */

/** A teacher's brief as `/auth/me` returns it — note the name is "Early Years". */
const EARLY_YEARS: ViewerSection = {
  id: "sec-ey", name: "Early Years", report_key: "nursery-report",
};
const PRIMARY: ViewerSection = {
  id: "sec-pr", name: "Primary", report_key: "junior-report",
};
const SECONDARY: ViewerSection = {
  id: "sec-se", name: "Secondary", report_key: "secondary-report",
};

describe("report section keys", () => {
  it("lists the three sections senior first, as Educare does", () => {
    expect([...REPORT_SECTION_KEYS]).toEqual([
      "secondary-report", "junior-report", "nursery-report",
    ]);
  });

  it("recognises only those three", () => {
    expect(isReportSectionKey("nursery-report")).toBe(true);
    // The old key, renamed to Junior. If it lingered anywhere it would be a
    // section the server never names, i.e. a permanently hidden one.
    expect(isReportSectionKey("primary-report")).toBe(false);
    expect(isReportSectionKey("academics")).toBe(false);
    expect(isReportSectionKey("")).toBe(false);
    expect(isReportSectionKey(null)).toBe(false);
    expect(isReportSectionKey(undefined)).toBe(false);
  });
});

describe("visibleReportKeys", () => {
  it("resolves an Early Years teacher to the Nursery report section", () => {
    // THE BUG, as a test. The section is not called "Nursery" and never was.
    expect(EARLY_YEARS.name).not.toBe("Nursery");
    expect(visibleReportKeys([EARLY_YEARS])).toEqual(new Set(["nursery-report"]));
  });

  it("ignores the section's name entirely", () => {
    // Same key, a name that matches nothing. A name-based rule returns empty here.
    const renamed = { ...EARLY_YEARS, name: "Foundation Stage" };
    expect(visibleReportKeys([renamed])).toEqual(new Set(["nursery-report"]));
  });

  it("handles a teacher who spans two levels", () => {
    expect(visibleReportKeys([PRIMARY, SECONDARY])).toEqual(
      new Set(["junior-report", "secondary-report"]),
    );
  });

  it("returns null — not an empty set — when nothing classifies", () => {
    // The distinction is load-bearing: an empty set means "matches nothing" and
    // a caller would hide every report section. null means "cannot tell".
    expect(visibleReportKeys([{ id: "x", name: "Sixth Form", report_key: null }])).toBeNull();
    expect(visibleReportKeys([{ id: "x", name: "Sixth Form" }])).toBeNull();
    expect(visibleReportKeys([])).toBeNull();
    expect(visibleReportKeys(null)).toBeNull();
    expect(visibleReportKeys(undefined)).toBeNull();
  });

  it("drops an unknown key rather than trusting it", () => {
    // A server that learns a fourth key must not make it visible here by accident.
    expect(visibleReportKeys([{ id: "x", report_key: "sixth-form-report" }])).toBeNull();
  });

  it("keeps the classifiable sections when one of several is unresolved", () => {
    const partial = [SECONDARY, { id: "y", name: "Middle", report_key: null }];
    expect(visibleReportKeys(partial)).toEqual(new Set(["secondary-report"]));
  });
});

describe("reportSectionVisible", () => {
  it("shows an Early Years teacher the Nursery section and hides the others", () => {
    const allowed = visibleReportKeys([EARLY_YEARS]);
    expect(reportSectionVisible("nursery-report", allowed)).toBe(true);
    expect(reportSectionVisible("junior-report", allowed)).toBe(false);
    expect(reportSectionVisible("secondary-report", allowed)).toBe(false);
  });

  it("shows every report section when the scope cannot be resolved", () => {
    // Fail open. One report section too many is noise; none is the bug.
    for (const key of REPORT_SECTION_KEYS) {
      expect(reportSectionVisible(key, null)).toBe(true);
    }
  });

  it("never hides a section that is not a report section", () => {
    // This function decides report scoping only. If it ever became the thing
    // that hid Academics or Students, the blast radius would be the whole nav.
    const allowed = visibleReportKeys([EARLY_YEARS]);
    for (const key of ["academics", "students", "cbt", "finance", "hr-manager"]) {
      expect(reportSectionVisible(key, allowed)).toBe(true);
    }
  });

  it("is unaffected by section renames", () => {
    // The generalisation of the bug: Primary and Secondary matched only because
    // their names happened to equal the literals. Rename every section and the
    // visibility answer must not move.
    const renamed = [
      { ...EARLY_YEARS, name: "Nursery" },
      { ...PRIMARY, name: "Junior" },
      { ...SECONDARY, name: "Senior School" },
    ];
    const before = visibleReportKeys([EARLY_YEARS, PRIMARY, SECONDARY]);
    expect(visibleReportKeys(renamed)).toEqual(before);
  });
});
