import { describe, expect, it } from "vitest";
import { formatMark } from "@/lib/reportEntry";

// A live parent report card rendered "62.70341089190804 / 100". Scores are raw
// floats and a CBT percentage is a division, so the unformatted value landed
// straight on a document a parent reads.

describe("formatMark", () => {
  it("cuts a raw percentage down to what belongs on a report card", () => {
    expect(formatMark(62.70341089190804)).toBe("62.7");
    expect(formatMark(38.04763854186277)).toBe("38.05");
  });

  it("drops trailing zeros so a clean mark reads as a whole number", () => {
    // "70.00 / 100.00" looks like false precision on a printed card.
    expect(formatMark(70)).toBe("70");
    expect(formatMark(100.0)).toBe("100");
    expect(formatMark(62.5)).toBe("62.5");
  });

  it("rounds rather than truncates", () => {
    expect(formatMark(62.999)).toBe("63");
    expect(formatMark(0.005)).toBe("0.01");
  });

  it("uses the same em-dash the tables already show for a missing mark", () => {
    expect(formatMark(null)).toBe("—");
    expect(formatMark(undefined)).toBe("—");
    expect(formatMark("")).toBe("—");
  });

  it("keeps a real zero, which is a mark and not a missing one", () => {
    // `score ?? "—"` was right about null but a naive falsy check would hide 0.
    expect(formatMark(0)).toBe("0");
  });

  it("accepts the string form an API may serialise a decimal as", () => {
    expect(formatMark("62.70341089190804")).toBe("62.7");
    expect(formatMark("88")).toBe("88");
  });

  it("does not render NaN or Infinity at a parent", () => {
    expect(formatMark(NaN)).toBe("—");
    expect(formatMark(Infinity)).toBe("—");
    expect(formatMark("not a number")).toBe("—");
  });
});
