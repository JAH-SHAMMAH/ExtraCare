import { describe, expect, it } from "vitest";

import { classLabel } from "../lib/classLabel";

/**
 * The reported faults, as tests.
 *
 * The chart built `${name} ${section}` where `section` is the arm, so 24 of
 * Fairview's 31 classes printed their arm twice ("YEAR 1 A A") and 6 Early Years
 * classes gained an arm Educare does not give them. Counts and class names here
 * are the real ones, read from the production dump at head 138.
 */

/** Every distinct (name, arm) shape in production. */
const PRODUCTION: Array<[string, string | null]> = [
  ["Year 1 A", "A"], ["Year 1 B", "B"], ["Year 2 A", "A"], ["Year 2 B", "B"],
  ["Year 3 A", "A"], ["Year 3 B", "B"], ["Year 4 A", "A"], ["Year 4 B", "B"],
  ["Year 5 A", "A"], ["Year 5 B", "B"], ["Year 6 A", "A"], ["Year 6 B", "B"],
  ["Year 7 A", "A"], ["Year 7 B", "B"], ["Year 8 A", "A"], ["Year 8 B", "B"],
  ["Year 9 A", "A"], ["Year 9 B", "B"], ["Year 10 A", "A"], ["Year 10 B", "B"],
  ["Year 11 A", "A"], ["Year 11 B", "B"], ["Year 12 A", "A"], ["Year 12 B", "B"],
  ["Nursery Blossom", "B"], ["Nursery Maples", "A"],
  ["Pre-Nursery Lilac", "A"], ["Pre-Nursery Lillies", "B"],
  ["Reception Olive", "A"], ["Reception Tulip", "B"],
  ["Playgroup", null],
];

describe("classLabel — the doubling", () => {
  it("does not repeat an arm the name already ends in", () => {
    expect(classLabel({ name: "Year 1 A", section: "A" })).toBe("Year 1 A");
    expect(classLabel({ name: "Year 6 B", section: "B" })).toBe("Year 6 B");
  });

  it("fixes all 24 of the classes that doubled", () => {
    const doubling = PRODUCTION.filter(
      ([name, arm]) => arm && name.toLowerCase().endsWith(` ${arm.toLowerCase()}`),
    );
    expect(doubling).toHaveLength(24);
    for (const [name, section] of doubling) {
      expect(classLabel({ name, section })).toBe(name);
    }
  });

  it("never changes the casing", () => {
    // "as stored" and "uppercased" are different instructions. The chart's own
    // tickFormatter uppercase is what turned "Year 1 A A" into "YEAR 1 A A".
    expect(classLabel({ name: "Year 10 A", section: "A" })).toBe("Year 10 A");
    expect(classLabel({ name: "year 10 a", section: "A" })).toBe("year 10 a");
  });

  it("matches the arm case-insensitively", () => {
    expect(classLabel({ name: "Year 1 a", section: "A" })).toBe("Year 1 a");
    expect(classLabel({ name: "YEAR 1 A", section: "a" })).toBe("YEAR 1 A");
  });

  it("handles an arm joined to the name with no space", () => {
    // "Year 1A" is a plausible hand-typed form; the boundary before the arm is a
    // digit, not a letter, so it still counts as already-suffixed.
    expect(classLabel({ name: "Year 1A", section: "A" })).toBe("Year 1A");
  });

  it("does not mistake the tail of a word for an arm", () => {
    // A bare endsWith would swallow this: "Maples" ends in "s".
    expect(classLabel({ name: "Nursery Maples", section: "S" })).toBe("Nursery Maples S");
    // And the "A" inside "YEAR" must never match.
    expect(classLabel({ name: "Year 10 B", section: "A" })).toBe("Year 10 B A");
  });
});

describe("classLabel — arms and names that are missing", () => {
  it("renders a class with no arm bare", () => {
    // Playgroup: the one production class with no arm stored.
    expect(classLabel({ name: "Playgroup", section: null })).toBe("Playgroup");
    expect(classLabel({ name: "Playgroup" })).toBe("Playgroup");
    expect(classLabel({ name: "Playgroup", section: "" })).toBe("Playgroup");
    expect(classLabel({ name: "Playgroup", section: "   " })).toBe("Playgroup");
  });

  it("trims", () => {
    expect(classLabel({ name: "  Year 1 A  ", section: " A " })).toBe("Year 1 A");
  });

  it("survives a missing name or a missing class", () => {
    // An empty axis tick reads as a rendering fault, so the arm is better than
    // nothing — but neither may throw.
    expect(classLabel({ name: "", section: "A" })).toBe("A");
    expect(classLabel({})).toBe("");
    expect(classLabel(null)).toBe("");
    expect(classLabel(undefined)).toBe("");
  });
});

describe("classLabel — what it deliberately does not fix", () => {
  it("still appends a spurious arm to an Early Years name", () => {
    // DOCUMENTED LIMIT, not an oversight. "Reception Olive" genuinely does not
    // end in "A", and no display rule can tell a redundant arm from a real one
    // when the name does not contain it. These 6 rows are wrong data — Educare
    // has no A/B for Early Years — and clearing `section` belongs with the
    // rename. If this expectation ever changes, the rename has happened.
    expect(classLabel({ name: "Reception Olive", section: "A" })).toBe("Reception Olive A");
    expect(classLabel({ name: "Nursery Blossom", section: "B" })).toBe("Nursery Blossom B");

    const spurious = PRODUCTION.filter(
      ([name, arm]) => arm && !name.toLowerCase().endsWith(` ${arm.toLowerCase()}`),
    );
    expect(spurious).toHaveLength(6);
  });

  it("handles Educare's real names once they land", () => {
    // Post-rename, the arm is redundant for ALL 31 — the rename clears it. Until
    // it does, a word-arm that IS the suffix is still recognised.
    expect(classLabel({ name: "YEAR 6 PEARL", section: "PEARL" })).toBe("YEAR 6 PEARL");
    expect(classLabel({ name: "RECEPTION OLIVES", section: "" })).toBe("RECEPTION OLIVES");
    // ...and one that is not would be appended, which is why clearing matters.
    expect(classLabel({ name: "YEAR 6 PEARL", section: "A" })).toBe("YEAR 6 PEARL A");
  });
});
