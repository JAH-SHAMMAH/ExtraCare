import { describe, expect, it } from "vitest";
import { subTermDisplay, type GridAssessment } from "@/lib/reportEntry";

// The Make Report grid is built from ALL of a term's assessments: the backend
// filters by term and class level, never by sub-term. So a term carrying both a
// Half-Term and a Full-Term "EXAM" produces two columns whose names are
// identical. The API has always sent sub_term_name; the grid simply never
// rendered it, leaving the teacher no way to tell which column they were
// filling in. These pin the rule that fixes that.

const a = (name: string, sub: string | null): GridAssessment => ({
  id: `${name}-${sub}`, name, max_score: 100, sub_term_name: sub,
});

describe("subTermDisplay", () => {
  it("labels every column when the grid mixes sub-terms — the ambiguous case", () => {
    const out = subTermDisplay([a("EXAM", "Half-Term"), a("EXAM", "Full-Term")]);
    expect(out.perColumn).toBe(true);
    // No single caption: there is no one sub-term to name.
    expect(out.only).toBeNull();
  });

  it("names the sub-term once when the whole grid shares one", () => {
    const out = subTermDisplay([a("CBT", "Full-Term"), a("EXAM", "Full-Term")]);
    // Repeating "Full-Term" across every header would be noise, not information.
    expect(out.perColumn).toBe(false);
    expect(out.only).toBe("Full-Term");
  });

  it("says nothing when no sub-term is recorded", () => {
    expect(subTermDisplay([a("EXAM", null)])).toEqual({ perColumn: false, only: null });
  });

  it("treats a partially-labelled grid as unambiguous on the one known name", () => {
    // One assessment lacks a sub-term; the rest agree. Nothing to disambiguate
    // between, so the known name is surfaced once rather than per column.
    const out = subTermDisplay([a("CBT", null), a("EXAM", "Half-Term")]);
    expect(out).toEqual({ perColumn: false, only: "Half-Term" });
  });

  it("handles an empty or absent grid without throwing", () => {
    expect(subTermDisplay([])).toEqual({ perColumn: false, only: null });
    expect(subTermDisplay(undefined)).toEqual({ perColumn: false, only: null });
    expect(subTermDisplay(null)).toEqual({ perColumn: false, only: null });
  });

  it("is unaffected by how many assessments share a sub-term", () => {
    const many = Array.from({ length: 5 }, (_, i) => a(`A${i}`, "Full-Term"));
    expect(subTermDisplay(many)).toEqual({ perColumn: false, only: "Full-Term" });
    expect(subTermDisplay([...many, a("EXAM", "Half-Term")]).perColumn).toBe(true);
  });
});
