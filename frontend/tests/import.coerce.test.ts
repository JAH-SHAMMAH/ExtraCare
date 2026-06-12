import { describe, it, expect } from "vitest";
import { coerceDate, coerceGender, toLowerTrim, trimString } from "@/lib/import/coerce";

describe("coerceDate", () => {
  it("passes through ISO format", () => {
    expect(coerceDate("2010-05-14")).toBe("2010-05-14");
  });

  it("normalizes DD/MM/YYYY (African default)", () => {
    expect(coerceDate("14/05/2010")).toBe("2010-05-14");
  });

  it("normalizes DD-MM-YYYY", () => {
    expect(coerceDate("14-05-2010")).toBe("2010-05-14");
  });

  it("normalizes DD.MM.YYYY", () => {
    expect(coerceDate("14.05.2010")).toBe("2010-05-14");
  });

  it("detects MM/DD/YYYY when day > 12", () => {
    // "05/14/2010" — second component is 14, can't be a month
    expect(coerceDate("05/14/2010")).toBe("2010-05-14");
  });

  it("detects DD/MM/YYYY when first > 12", () => {
    expect(coerceDate("25/03/2010")).toBe("2010-03-25");
  });

  it("handles YYYY/MM/DD", () => {
    expect(coerceDate("2010/05/14")).toBe("2010-05-14");
  });

  it("pads single-digit months and days", () => {
    expect(coerceDate("5/7/2010")).toBe("2010-07-05");
  });

  it("returns original on unparseable input", () => {
    expect(coerceDate("not a date")).toBe("not a date");
  });

  it("returns undefined for empty string (date field accepts undefined)", () => {
    expect(coerceDate("")).toBe(undefined);
  });

  it("returns undefined for whitespace-only", () => {
    expect(coerceDate("  ")).toBe(undefined);
  });

  it("rejects impossible month", () => {
    expect(coerceDate("2010-13-14")).toBe("2010-13-14");
  });

  it("rejects out-of-range year", () => {
    expect(coerceDate("14/05/1800")).toBe("14/05/1800");
  });
});

describe("coerceGender", () => {
  it("handles canonical lowercase", () => {
    expect(coerceGender("male")).toBe("male");
    expect(coerceGender("female")).toBe("female");
    expect(coerceGender("other")).toBe("other");
  });

  it("handles Title Case", () => {
    expect(coerceGender("Male")).toBe("male");
    expect(coerceGender("Female")).toBe("female");
  });

  it("handles UPPERCASE", () => {
    expect(coerceGender("MALE")).toBe("male");
    expect(coerceGender("FEMALE")).toBe("female");
  });

  it("handles single-letter codes", () => {
    expect(coerceGender("M")).toBe("male");
    expect(coerceGender("F")).toBe("female");
    expect(coerceGender("O")).toBe("other");
    expect(coerceGender("m")).toBe("male");
    expect(coerceGender("f")).toBe("female");
  });

  it("returns undefined for empty (gender schema is optional enum)", () => {
    expect(coerceGender("")).toBe(undefined);
  });

  it("passes through unrecognized value for Zod to reject", () => {
    expect(coerceGender("nonbinary")).toBe("nonbinary");
  });
});

describe("toLowerTrim", () => {
  it("lowercases and trims", () => {
    expect(toLowerTrim("  Ada@Example.COM ")).toBe("ada@example.com");
  });
  it("returns empty string for empty (schema accepts '' via .or(z.literal('')))", () => {
    expect(toLowerTrim("   ")).toBe("");
    expect(toLowerTrim("")).toBe("");
  });
});

describe("trimString", () => {
  it("trims", () => {
    expect(trimString("  hello  ")).toBe("hello");
  });
  it("returns empty string for empty (schema accepts '' via .or(z.literal('')))", () => {
    expect(trimString("")).toBe("");
    expect(trimString("   ")).toBe("");
  });
  it("passes non-strings through unchanged", () => {
    expect(trimString(undefined)).toBe(undefined);
    expect(trimString(null)).toBe(null);
  });
});
