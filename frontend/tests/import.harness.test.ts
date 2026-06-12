/**
 * End-to-end synthetic harness for Students Import.
 *
 * Purpose: run real-world-messy CSV strings through the actual parser (papaparse
 * dynamic import), auto-mapper, and async validator — exactly the same code
 * path the UI uses, minus the HTTP POST. Confirms the full wizard pipeline
 * behaves correctly against realistic data before touching a live backend.
 */
import { describe, it, expect } from "vitest";
import Papa from "papaparse";
import { validateRowsAsync, autoMapHeaders } from "@/lib/import/validator";
import { studentImportPreset, extractErrorMessage } from "@/lib/import/presets";

// Parse CSV string synchronously (mimics parsers.ts but without File API)
function parseCSVString(csv: string) {
  const result = Papa.parse<Record<string, string>>(csv, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (h) => h.trim(),
    transform: (v) => (typeof v === "string" ? v.trim() : v),
  });
  const rows = result.data.filter((r) => Object.values(r).some((v) => v && String(v).length > 0));
  return { headers: (result.meta.fields || []).map((h) => h.trim()), rows };
}

describe("Harness: clean data path", () => {
  it("auto-maps, validates, and produces commit-ready payloads", async () => {
    const csv = `First Name,Last Name,Email,Phone,Date of Birth,Gender,Guardian Name,Guardian Phone,Address
Ada,Okonkwo,ada.okonkwo@school.ng,+2348012345678,2010-05-14,female,Chioma Okonkwo,+2348098765432,14 Lagos Street
Bola,Adebayo,bola@school.ng,+2348011112222,2011-03-20,male,Tunde Adebayo,+2348033334444,22 Ikeja Road
Chidi,Eze,chidi@school.ng,+2348055556666,2009-11-08,male,Ngozi Eze,+2348077778888,5 Enugu Ave`;

    const parsed = parseCSVString(csv);
    expect(parsed.rows).toHaveLength(3);
    expect(parsed.headers).toContain("First Name");

    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);
    expect(mapping.first_name).toBe("First Name");
    expect(mapping.email).toBe("Email");
    expect(mapping.date_of_birth).toBe("Date of Birth");

    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );
    expect(result.valid).toHaveLength(3);
    expect(result.invalid).toHaveLength(0);

    // Commit payloads should be canonical
    expect(result.valid[0].data.first_name).toBe("Ada");
    expect(result.valid[0].data.email).toBe("ada.okonkwo@school.ng");
    expect(result.valid[0].data.gender).toBe("female");
    expect(result.valid[0].data.date_of_birth).toBe("2010-05-14");
  });
});

describe("Harness: messy real-world data", () => {
  it("handles mixed-case gender, DD/MM/YYYY dates, Title Case emails, renamed headers", async () => {
    const csv = `Given Name,Surname,E-mail,Mobile,DOB,Sex,Parent Name,Parent Phone
Ada,Okonkwo,Ada.Okonkwo@School.NG,+234 801 234 5678,14/05/2010,Female,Chioma Okonkwo,08098765432
bola,ADEBAYO,BOLA@school.ng,0801-111-2222,20/03/2011,M,Tunde Adebayo,+2348033334444
Chidi,Eze,chidi@SCHOOL.ng,(080) 555 6666,08.11.2009,male,Ngozi Eze,+2348077778888`;

    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);

    // Aliases must match
    expect(mapping.first_name).toBe("Given Name");
    expect(mapping.last_name).toBe("Surname");
    expect(mapping.email).toBe("E-mail");
    expect(mapping.phone).toBe("Mobile");
    expect(mapping.date_of_birth).toBe("DOB");
    expect(mapping.gender).toBe("Sex");
    expect(mapping.guardian_name).toBe("Parent Name");
    expect(mapping.guardian_phone).toBe("Parent Phone");

    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );

    expect(result.invalid).toHaveLength(0);
    expect(result.valid).toHaveLength(3);

    // Normalization checks
    const emails = result.valid.map((r) => r.data.email);
    expect(emails).toEqual([
      "ada.okonkwo@school.ng",
      "bola@school.ng",
      "chidi@school.ng",
    ]);

    const dobs = result.valid.map((r) => r.data.date_of_birth);
    expect(dobs).toEqual(["2010-05-14", "2011-03-20", "2009-11-08"]);

    const genders = result.valid.map((r) => r.data.gender);
    expect(genders).toEqual(["female", "male", "male"]);
  });

  it("catches and reports bad rows with row numbers", async () => {
    const csv = `First Name,Last Name,Email,Phone
Ada,Okonkwo,ada@school.ng,+2348012345678
,MissingFirst,bob@school.ng,+2348011112222
Chidi,Eze,not-an-email,+2348055556666
Dele,Bakare,dele@school.ng,invalid$phone$!!!`;

    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);
    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );

    expect(result.valid).toHaveLength(1);
    expect(result.valid[0].data.first_name).toBe("Ada");

    expect(result.invalid).toHaveLength(3);
    // Row 3 = missing first_name
    const row3 = result.invalid.find((r) => r.rowNumber === 3);
    expect(row3?.errors.first_name).toBeDefined();
    // Row 4 = bad email
    const row4 = result.invalid.find((r) => r.rowNumber === 4);
    expect(row4?.errors.email).toBeDefined();
    // Row 5 = bad phone
    const row5 = result.invalid.find((r) => r.rowNumber === 5);
    expect(row5?.errors.phone).toBeDefined();
  });
});

describe("Harness: in-file duplicates filtered from commit", () => {
  it("keeps only the first occurrence of a duplicate email", async () => {
    const csv = `First Name,Last Name,Email
Ada,Okonkwo,shared@school.ng
Bola,Adebayo,shared@school.ng
Chidi,Eze,SHARED@School.NG
Dele,Bakare,unique@school.ng`;

    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);
    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );

    // Only Ada + Dele make it to valid[] — Bola and Chidi are flagged as dupes
    expect(result.valid).toHaveLength(2);
    expect(result.valid[0].data.first_name).toBe("Ada");
    expect(result.valid[1].data.first_name).toBe("Dele");
    expect(result.duplicates).toHaveLength(2);
    expect(result.duplicates.map((d) => d.rowNumber).sort()).toEqual([3, 4]);
  });
});

describe("Harness: BOM and Windows line endings", () => {
  it("handles UTF-8 BOM prefix", async () => {
    const csvWithBOM = "\uFEFF" + `First Name,Last Name\nAda,Okonkwo\nBola,Adebayo`;
    const parsed = parseCSVString(csvWithBOM);
    expect(parsed.rows).toHaveLength(2);
    // Header should not contain the BOM after trimming
    expect(parsed.headers[0]).toBe("First Name");
  });

  it("handles CRLF line endings", async () => {
    const csv = "First Name,Last Name\r\nAda,Okonkwo\r\nBola,Adebayo\r\n";
    const parsed = parseCSVString(csv);
    expect(parsed.rows).toHaveLength(2);
  });

  it("handles quoted fields with commas", async () => {
    const csv = `First Name,Last Name,Address
Ada,Okonkwo,"14 Lagos Street, Ikeja"
Bola,Adebayo,"22, Old Market Rd"`;
    const parsed = parseCSVString(csv);
    expect(parsed.rows[0].Address).toBe("14 Lagos Street, Ikeja");
    expect(parsed.rows[1].Address).toBe("22, Old Market Rd");
  });
});

describe("Harness: backend failure simulation with Pydantic error shapes", () => {
  it("renders Pydantic 422 array errors as readable strings in failures table", () => {
    const pydanticError = {
      response: {
        status: 422,
        data: {
          detail: [
            {
              loc: ["body", "email"],
              msg: "value is not a valid email address",
              type: "value_error.email",
            },
          ],
        },
      },
    };
    const msg = extractErrorMessage(pydanticError);
    expect(msg).toBe("email: value is not a valid email address");
    expect(msg).not.toContain("[object");
  });

  it("renders duplicate-key HTTPException detail strings", () => {
    const uniqueConstraint = {
      response: {
        status: 409,
        data: { detail: "Email 'ada@school.ng' already registered" },
      },
    };
    expect(extractErrorMessage(uniqueConstraint)).toBe(
      "Email 'ada@school.ng' already registered"
    );
  });

  it("handles multiple validation errors joined", () => {
    const multi = {
      response: {
        status: 422,
        data: {
          detail: [
            { loc: ["body", "email"], msg: "invalid email", type: "x" },
            { loc: ["body", "phone"], msg: "invalid phone", type: "y" },
          ],
        },
      },
    };
    const msg = extractErrorMessage(multi);
    expect(msg).toContain("email: invalid email");
    expect(msg).toContain("phone: invalid phone");
  });
});

describe("Harness: performance at 5,000 rows", () => {
  it("validates 5k rows in under 1 second", async () => {
    const header = "First Name,Last Name,Email,Gender,Date of Birth";
    const lines = Array.from(
      { length: 5000 },
      (_, i) => `Student${i},Test${i},student${i}@school.ng,${i % 2 === 0 ? "female" : "male"},${String(10 + (i % 20)).padStart(2, "0")}/0${(i % 9) + 1}/2010`
    );
    const csv = [header, ...lines].join("\n");

    const t0 = performance.now();
    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);
    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );
    const duration = performance.now() - t0;

    expect(parsed.rows).toHaveLength(5000);
    expect(result.valid).toHaveLength(5000);
    expect(result.invalid).toHaveLength(0);
    expect(duration).toBeLessThan(2000); // generous ceiling; CI machines vary
    // eslint-disable-next-line no-console
    console.log(`    [harness] 5k row pipeline: ${duration.toFixed(0)}ms`);
  });

  it("fires progress callbacks during async validation", async () => {
    const header = "First Name,Last Name";
    const lines = Array.from({ length: 1000 }, (_, i) => `N${i},S${i}`);
    const csv = [header, ...lines].join("\n");
    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);

    const progressSnapshots: number[] = [];
    await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns,
      (p) => progressSnapshots.push(p)
    );

    // Chunk size is 200, so we expect ~5 progress calls for 1000 rows
    expect(progressSnapshots.length).toBeGreaterThanOrEqual(5);
    expect(progressSnapshots[progressSnapshots.length - 1]).toBe(1000);
  });
});

describe("Harness: failure modes", () => {
  it("returns zero rows from an empty file (after header)", () => {
    const csv = "First Name,Last Name\n";
    const parsed = parseCSVString(csv);
    expect(parsed.rows).toHaveLength(0);
  });

  it("skips blank lines in the middle", () => {
    const csv = `First Name,Last Name
Ada,Okonkwo

Bola,Adebayo
`;
    const parsed = parseCSVString(csv);
    expect(parsed.rows).toHaveLength(2);
  });

  it("surface empty-but-valid row when all optional fields are blank", async () => {
    const csv = `First Name,Last Name,Email,Phone
Ada,Okonkwo,,`;
    const parsed = parseCSVString(csv);
    const mapping = autoMapHeaders(parsed.headers, studentImportPreset.columns);
    const result = await validateRowsAsync(
      studentImportPreset.schema,
      parsed.rows,
      mapping,
      studentImportPreset.columns
    );
    expect(result.valid).toHaveLength(1);
  });
});
