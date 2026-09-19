import { describe, expect, it } from "vitest";
import {
  classesFromAssignments, defaultSubTermId, subjectsForClass,
  type NamedRow, type TeachingAssignment,
} from "@/lib/reportEntry";

// Make Report offered one combined "class · subject" dropdown. For a Fairview
// teacher (2 classes x 10 subjects) that is 20 entries in one list. These pin the
// split into Class + Subject, and the rule that Subject depends on Class.

const a = (c: string, cn: string, s: string, sn: string): TeachingAssignment => ({
  class_id: c, class_name: cn, subject_id: s, subject_name: sn,
});

const DENSE: TeachingAssignment[] = [
  a("c2", "Year 11 Beryl", "s2", "Mathematics"),
  a("c1", "Year 10 Amethyst", "s1", "English"),
  a("c1", "Year 10 Amethyst", "s2", "Mathematics"),
  a("c2", "Year 11 Beryl", "s1", "English"),
];

describe("classesFromAssignments", () => {
  it("de-duplicates the pairs down to distinct classes, in name order", () => {
    expect(classesFromAssignments(DENSE)).toEqual([
      { id: "c1", name: "Year 10 Amethyst" },
      { id: "c2", name: "Year 11 Beryl" },
    ]);
  });

  it("returns nothing for a teacher with no assignments", () => {
    expect(classesFromAssignments([])).toEqual([]);
    expect(classesFromAssignments(undefined)).toEqual([]);
    expect(classesFromAssignments(null)).toEqual([]);
  });
});

describe("subjectsForClass", () => {
  it("offers only the subjects taught in the chosen class", () => {
    // The sparse case this exists for: Maths in Year 10 only.
    const sparse = [a("c1", "Year 10", "s1", "English"), a("c1", "Year 10", "s2", "Maths"),
                    a("c2", "Year 11", "s1", "English")];
    expect(subjectsForClass(sparse, "c2").map((s) => s.name)).toEqual(["English"]);
    expect(subjectsForClass(sparse, "c1").map((s) => s.name)).toEqual(["English", "Maths"]);
  });

  it("returns every subject when the timetable is dense, as Fairview's is today", () => {
    expect(subjectsForClass(DENSE, "c1").map((s) => s.name)).toEqual(["English", "Mathematics"]);
    expect(subjectsForClass(DENSE, "c2").map((s) => s.name)).toEqual(["English", "Mathematics"]);
  });

  it("returns nothing for a class the teacher does not teach", () => {
    // Guards the pair the grid endpoint would answer with a 403.
    expect(subjectsForClass(DENSE, "c-other")).toEqual([]);
    expect(subjectsForClass(DENSE, "")).toEqual([]);
  });
});

describe("defaultSubTermId", () => {
  const rows = (...names: string[]): NamedRow[] =>
    names.map((n, i) => ({ id: `st${i}`, name: n }));

  it("prefers Full-Term, so the grid shows what it showed before the selector existed", () => {
    expect(defaultSubTermId(rows("Half-Term", "Full-Term"))).toBe("st1");
  });

  it("tolerates the spellings the backend also accepts", () => {
    expect(defaultSubTermId(rows("Half-Term", "Full Term"))).toBe("st1");
    expect(defaultSubTermId(rows("half-term", "full_term"))).toBe("st1");
  });

  it("falls back to the first sub-term when no Full-Term is defined", () => {
    expect(defaultSubTermId(rows("Michaelmas", "Lent"))).toBe("st0");
  });

  it("returns an empty string when the school has no sub-terms", () => {
    // The caller sends no sub_term_id, and the grid returns the whole term.
    expect(defaultSubTermId([])).toBe("");
    expect(defaultSubTermId(undefined)).toBe("");
  });
});
