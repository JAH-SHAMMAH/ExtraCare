import { describe, expect, it } from "vitest";

import {
  allSessionsRows, currentSessionOf, currentSessionRows, isInCurrentSession,
  sessionsOf, type DistributionClass,
} from "../lib/classDistribution";

/**
 * The two reported chart faults, as tests, on the real production shape:
 * 30 classes holding '2025/2026' and one (Playgroup) holding NULL.
 */

const FAIRVIEW: DistributionClass[] = [
  { name: "Year 1 A", section: "A", academic_year: "2025/2026", student_count: 15 },
  { name: "Year 1 B", section: "B", academic_year: "2025/2026", student_count: 14 },
  { name: "Reception Olive", section: "A", academic_year: "2025/2026", student_count: 12 },
  // The one class with no academic_year. 0 pupils in production today.
  { name: "Playgroup", section: null, academic_year: null, student_count: 0 },
];

describe("a class with no academic_year", () => {
  it("still counts in the current session", () => {
    // THE FAULT. The filter was `c.academic_year === currentSession`, so this
    // row was dropped and the chart drew 30 bars for 31 classes.
    const rows = currentSessionRows(FAIRVIEW);
    expect(rows.map((r) => r.label)).toContain("Playgroup");
    expect(rows).toHaveLength(4);
  });

  it("contributes its pupils to the total", () => {
    // 0 in production, so the old total was accidentally right. Give the class
    // a pupil and the old behaviour loses them with no empty state to explain it.
    const withPupils = FAIRVIEW.map((c) =>
      c.name === "Playgroup" ? { ...c, student_count: 7 } : c);
    const total = currentSessionRows(withPupils).reduce((s, r) => s + r.students, 0);
    expect(total).toBe(15 + 14 + 12 + 7);
  });

  it("does not make an unknown year belong to a NAMED other session", () => {
    // The rule is "unknown means current", not "unknown matches everything".
    expect(isInCurrentSession({ academic_year: "2024/2025" }, "2025/2026")).toBe(false);
    expect(isInCurrentSession({ academic_year: null }, "2025/2026")).toBe(true);
  });

  it("treats everything as current when no session is resolvable", () => {
    // Every row NULL: there is no other session to belong to, and an empty
    // chart would be wrong.
    const none: DistributionClass[] = [
      { name: "Playgroup", academic_year: null, student_count: 3 },
      { name: "Year 1 A", section: "A", academic_year: null, student_count: 4 },
    ];
    expect(currentSessionOf(none)).toBeNull();
    expect(currentSessionRows(none)).toHaveLength(2);
  });

  it("excludes a genuinely older session", () => {
    const withPast: DistributionClass[] = [
      ...FAIRVIEW,
      { name: "Year 1 A", section: "A", academic_year: "2024/2025", student_count: 99 },
    ];
    expect(currentSessionOf(withPast)).toBe("2025/2026");
    const rows = currentSessionRows(withPast);
    expect(rows.reduce((s, r) => s + r.students, 0)).toBe(15 + 14 + 12 + 0);
  });
});

describe("labels come from the shared helper", () => {
  it("does not double an arm the name already carries", () => {
    const rows = currentSessionRows(FAIRVIEW);
    expect(rows.map((r) => r.label)).toEqual([
      "Playgroup", "Reception Olive A", "Year 1 A", "Year 1 B",
    ]);
    // The reported symptom, asserted as absent.
    expect(rows.map((r) => r.label)).not.toContain("Year 1 A A");
  });

  it("sorts numerically so Year 10 follows Year 9", () => {
    const many: DistributionClass[] = [
      { name: "Year 10 A", section: "A", academic_year: "2025/2026", student_count: 1 },
      { name: "Year 9 A", section: "A", academic_year: "2025/2026", student_count: 1 },
      { name: "Year 2 A", section: "A", academic_year: "2025/2026", student_count: 1 },
    ];
    expect(currentSessionRows(many).map((r) => r.label))
      .toEqual(["Year 2 A", "Year 9 A", "Year 10 A"]);
  });
});

describe("the All sessions view", () => {
  it("reports the current session only, not a fabricated history", () => {
    // It used to group by the free-text academic_year, giving one bar labelled
    // "1 session on record" while two sessions existed. Grouping by
    // academic_sessions instead would be worse: student_count is the CURRENT
    // roster, so each year's bar would repeat the same pupils.
    const rows = allSessionsRows(FAIRVIEW);
    expect(rows).toHaveLength(1);
    expect(rows[0].label).toBe("2025/2026");
    expect(rows[0].students).toBe(41);
    expect(rows[0].classes).toBe(4);
  });

  it("agrees exactly with the current-session view", () => {
    // If these ever diverge, one of the two views is lying about the roster.
    const current = currentSessionRows(FAIRVIEW);
    const all = allSessionsRows(FAIRVIEW);
    expect(all[0].students).toBe(current.reduce((s, r) => s + r.students, 0));
    expect(all[0].classes).toBe(current.length);
  });

  it("has a label even with no session on any row", () => {
    const rows = allSessionsRows([{ name: "Playgroup", academic_year: null, student_count: 2 }]);
    expect(rows[0].label).toBe("Current session");
    expect(rows[0].students).toBe(2);
  });
});

describe("sessionsOf", () => {
  it("is newest-first and drops blanks", () => {
    expect(sessionsOf([
      { academic_year: "2024/2025" }, { academic_year: null },
      { academic_year: "2026/2027" }, { academic_year: "2024/2025" },
    ])).toEqual(["2026/2027", "2024/2025"]);
  });

  it("is empty for no classes", () => {
    expect(sessionsOf([])).toEqual([]);
    expect(currentSessionOf([])).toBeNull();
    expect(currentSessionRows([])).toEqual([]);
  });
});
