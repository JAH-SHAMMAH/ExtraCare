import { describe, it, expect } from "vitest";
import { validateRows, validateRowsAsync, autoMapHeaders, buildErrorsCSV } from "@/lib/import/validator";
import { studentImportPreset } from "@/lib/import/presets";

const { schema, columns } = studentImportPreset;

// Canonical mapping where CSV headers match preset labels exactly
const canonicalMapping: Record<string, string> = Object.fromEntries(
  columns.map((c) => [c.key, c.label])
);

function row(overrides: Record<string, string> = {}): Record<string, string> {
  return {
    "First Name": "Ada",
    "Last Name": "Okonkwo",
    Email: "",
    Phone: "",
    "Date of Birth": "",
    Gender: "",
    "Guardian Name": "",
    "Guardian Phone": "",
    Address: "",
    "Class ID": "",
    ...overrides,
  };
}

describe("validateRows — student preset", () => {
  it("accepts minimum valid row", () => {
    const result = validateRows(schema, [row()], canonicalMapping, columns);
    expect(result.valid).toHaveLength(1);
    expect(result.invalid).toHaveLength(0);
  });

  it("rejects row missing required first_name", () => {
    const result = validateRows(schema, [row({ "First Name": "" })], canonicalMapping, columns);
    expect(result.valid).toHaveLength(0);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0].errors).toHaveProperty("first_name");
  });

  it("numbers rows correctly (row 2 = first data row)", () => {
    const result = validateRows(schema, [row({ "First Name": "" })], canonicalMapping, columns);
    expect(result.invalid[0].rowNumber).toBe(2);
  });

  it("coerces Title Case gender to canonical lowercase", () => {
    const result = validateRows(schema, [row({ Gender: "Female" })], canonicalMapping, columns);
    expect(result.valid).toHaveLength(1);
    expect(result.valid[0].data.gender).toBe("female");
  });

  it("coerces 'F' shorthand gender", () => {
    const result = validateRows(schema, [row({ Gender: "F" })], canonicalMapping, columns);
    expect(result.valid[0].data.gender).toBe("female");
  });

  it("normalizes DD/MM/YYYY date to ISO", () => {
    const result = validateRows(schema, [row({ "Date of Birth": "14/05/2010" })], canonicalMapping, columns);
    expect(result.valid[0].data.date_of_birth).toBe("2010-05-14");
  });

  it("lowercases email", () => {
    const result = validateRows(schema, [row({ Email: "Ada@Example.COM" })], canonicalMapping, columns);
    expect(result.valid[0].data.email).toBe("ada@example.com");
  });

  it("rejects invalid email format", () => {
    const result = validateRows(schema, [row({ Email: "not-an-email" })], canonicalMapping, columns);
    expect(result.invalid).toHaveLength(1);
    expect(result.invalid[0].errors).toHaveProperty("email");
  });

  it("filters in-file email duplicates out of valid[] (first wins)", () => {
    const result = validateRows(
      schema,
      [
        row({ "First Name": "Ada", Email: "x@y.com" }),
        row({ "First Name": "Bob", Email: "X@Y.COM" }), // same email, different case
        row({ "First Name": "Cara", Email: "x@y.com" }),
      ],
      canonicalMapping,
      columns
    );
    expect(result.valid).toHaveLength(1);
    expect(result.valid[0].data.first_name).toBe("Ada");
    expect(result.duplicates).toHaveLength(2);
    expect(result.duplicates[0].rowNumber).toBe(3);
    expect(result.duplicates[1].rowNumber).toBe(4);
  });

  it("allows multiple rows with no email (no false dupe)", () => {
    const result = validateRows(
      schema,
      [row({ "First Name": "A" }), row({ "First Name": "B" }), row({ "First Name": "C" })],
      canonicalMapping,
      columns
    );
    expect(result.valid).toHaveLength(3);
    expect(result.duplicates).toHaveLength(0);
  });

  it("treats empty strings on optional fields as undefined", () => {
    const result = validateRows(schema, [row({ Phone: "", Email: "" })], canonicalMapping, columns);
    expect(result.valid).toHaveLength(1);
  });

  it("accepts Nigerian phone format with spaces", () => {
    const result = validateRows(schema, [row({ Phone: "+234 801 234 5678" })], canonicalMapping, columns);
    expect(result.valid).toHaveLength(1);
  });
});

describe("validateRowsAsync", () => {
  it("produces identical results to sync validator", async () => {
    const rows = [row(), row({ "First Name": "" }), row({ Email: "bad" })];
    const sync = validateRows(schema, rows, canonicalMapping, columns);
    const async_ = await validateRowsAsync(schema, rows, canonicalMapping, columns);
    expect(async_.valid.length).toBe(sync.valid.length);
    expect(async_.invalid.length).toBe(sync.invalid.length);
  });

  it("fires progress callback", async () => {
    const rows = Array.from({ length: 500 }, (_, i) => row({ "First Name": `Name${i}` }));
    const progressCalls: Array<[number, number]> = [];
    await validateRowsAsync(schema, rows, canonicalMapping, columns, (p, t) => progressCalls.push([p, t]));
    expect(progressCalls.length).toBeGreaterThan(0);
    expect(progressCalls[progressCalls.length - 1]).toEqual([500, 500]);
  });

  it("handles large row count without crashing", async () => {
    const rows = Array.from({ length: 5000 }, (_, i) =>
      row({ "First Name": `Name${i}`, Email: `student${i}@test.com` })
    );
    const result = await validateRowsAsync(schema, rows, canonicalMapping, columns);
    expect(result.valid.length).toBe(5000);
    expect(result.invalid.length).toBe(0);
  });
});

describe("autoMapHeaders", () => {
  it("matches exact label", () => {
    const mapping = autoMapHeaders(["First Name", "Last Name", "Email"], columns);
    expect(mapping.first_name).toBe("First Name");
    expect(mapping.last_name).toBe("Last Name");
    expect(mapping.email).toBe("Email");
  });

  it("matches aliases (DOB, Surname, Parent Name)", () => {
    const mapping = autoMapHeaders(["Given Name", "Surname", "DOB", "Parent Name"], columns);
    expect(mapping.first_name).toBe("Given Name");
    expect(mapping.last_name).toBe("Surname");
    expect(mapping.date_of_birth).toBe("DOB");
    expect(mapping.guardian_name).toBe("Parent Name");
  });

  it("is case and punctuation insensitive", () => {
    const mapping = autoMapHeaders(["first_name", "LAST-NAME", "e-mail"], columns);
    expect(mapping.first_name).toBe("first_name");
    expect(mapping.last_name).toBe("LAST-NAME");
    expect(mapping.email).toBe("e-mail");
  });

  it("leaves unmapped when no match", () => {
    const mapping = autoMapHeaders(["Random Column"], columns);
    expect(mapping.first_name).toBeUndefined();
  });
});

describe("buildErrorsCSV", () => {
  it("produces well-formed CSV", () => {
    const csv = buildErrorsCSV([
      { rowNumber: 3, raw: { email: "bad" }, errors: { email: "Valid email required" } },
    ]);
    expect(csv).toContain("row,field,error,value");
    expect(csv).toContain('"3"');
    expect(csv).toContain('"email"');
    expect(csv).toContain('"Valid email required"');
  });

  it("escapes quotes in error messages", () => {
    const csv = buildErrorsCSV([
      { rowNumber: 2, raw: { x: 'has "quotes"' }, errors: { x: 'bad "value"' } },
    ]);
    expect(csv).toContain('""quotes""');
  });
});
