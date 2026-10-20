import { describe, it, expect } from "vitest";
import { parseTeacherLines } from "@/lib/teacherBulk";

describe("parseTeacherLines", () => {
  it("parses the four Fairview lines in both comma and no-comma styles", () => {
    const rows = parseTeacherLines(
      "Mr Jeremiah CRS, secondary\nMs chiamaka Biology secondary\nMrs Juliet French primary\nMr Isaiah ICT primary",
    );
    expect(rows.map((r) => [r.title, r.first_name, r.subject, r.department])).toEqual([
      ["Mr", "Jeremiah", "CRS", "Secondary"],
      ["Ms", "chiamaka", "Biology", "Secondary"],
      ["Mrs", "Juliet", "French", "Primary"],
      ["Mr", "Isaiah", "ICT", "Primary"],
    ]);
  });
  it("handles Early Years, blank lines and a missing title", () => {
    const rows = parseTeacherLines("\nAda Phonics early years\n\n");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ title: "", first_name: "Ada", subject: "Phonics", department: "Early Years" });
  });
  it("never drops a line it cannot classify", () => {
    expect(parseTeacherLines("Chidi")).toHaveLength(1);
  });
});
