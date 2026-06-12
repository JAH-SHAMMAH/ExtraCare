// CSV parsing. Papaparse is dynamically imported so it's not in the main bundle.

export interface ParsedFile {
  headers: string[];
  rows: Record<string, string>[];
  /** Warnings surfaced by the parser (malformed rows, extra columns, etc.) */
  warnings: string[];
}

export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
export const MAX_ROWS = 5000;

export async function parseCSV(file: File): Promise<ParsedFile> {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    throw new Error(`File too large. Maximum size is ${MAX_FILE_SIZE_BYTES / 1024 / 1024} MB.`);
  }

  const Papa = (await import("papaparse")).default;

  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(file, {
      header: true,
      skipEmptyLines: "greedy",
      transformHeader: (h) => h.trim(),
      transform: (value) => (typeof value === "string" ? value.trim() : value),
      complete: (results) => {
        const rows = results.data.filter((r) => Object.values(r).some((v) => v && String(v).length > 0));

        if (rows.length === 0) {
          reject(new Error("The file is empty or contains no valid rows."));
          return;
        }
        if (rows.length > MAX_ROWS) {
          reject(new Error(`Too many rows. Maximum is ${MAX_ROWS.toLocaleString()} per file. Split your file and try again.`));
          return;
        }

        const headers = (results.meta.fields || []).map((h) => h.trim()).filter(Boolean);
        const warnings = (results.errors || [])
          .slice(0, 10)
          .map((e) => `Row ${typeof e.row === "number" ? e.row + 2 : "?"}: ${e.message}`);

        resolve({ headers, rows, warnings });
      },
      error: (err) => reject(new Error(err.message || "Failed to parse CSV file.")),
    });
  });
}
