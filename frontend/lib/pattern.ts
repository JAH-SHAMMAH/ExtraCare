import type { PatternDef } from "@/lib/api";

export const PATTERN_TYPES: { value: string; label: string }[] = [
  { value: "first_name", label: "First Name" }, { value: "surname", label: "Surname" }, { value: "other_name", label: "Other Name" },
  { value: "text", label: "Fixed text" }, { value: "year", label: "Year" }, { value: "level", label: "Level / Year group" },
  { value: "sequence", label: "Running number" },
];

const SAMPLE = { first_name: "Chidiebere", surname: "Ugwu", other_name: "Samuel", year: "2026", level: "JSS1", seq: 7 };

/** An example of what a pattern produces, so the Super User sees the result before saving. */
export function previewPattern(p: PatternDef, lower = false): string {
  const parts = p.items.map((it) => {
    switch (it.type) {
      case "first_name": case "surname": case "other_name": {
        const w = SAMPLE[it.type as "first_name"];
        return it.length === "full" || !it.length ? w : w.slice(0, Number(it.length));
      }
      case "text": return it.text ?? "";
      case "year": return SAMPLE.year;
      case "level": return SAMPLE.level;
      case "sequence": return String(SAMPLE.seq).padStart(Number(it.length) || 1, "0");
      default: return "";
    }
  });
  const out = parts.join(p.separator ?? "") + (p.suffix ?? "");
  return lower ? out.toLowerCase() : out;
}
