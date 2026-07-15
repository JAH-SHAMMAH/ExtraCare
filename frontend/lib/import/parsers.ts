// CSV parsing. Papaparse is dynamically imported so it's not in the main bundle.

export interface ParsedFile {
  headers: string[];
  rows: Record<string, string>[];
  /** Warnings surfaced by the parser (malformed rows, extra columns, etc.) */
  warnings: string[];
}

export const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
export const MAX_ROWS = 5000;

// File types the wizard accepts. CSV is parsed in-browser; the rest go to the
// server (/imports/parse-file), which reads Excel sheets and Word/PDF tables.
export const IMPORT_ACCEPT = ".csv,.xlsx,.docx,.pdf";

/** Parse any supported file into a ParsedFile. CSV stays client-side (unchanged);
 * Excel/Word/PDF are parsed server-side so no heavy parser ships in the bundle. */
export async function parseAnyFile(file: File): Promise<ParsedFile> {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    throw new Error(`File too large. Maximum size is ${MAX_FILE_SIZE_BYTES / 1024 / 1024} MB.`);
  }
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv")) return parseCSV(file);
  if (!/\.(xlsx|docx|pdf)$/.test(name)) {
    throw new Error("Unsupported file type. Upload a CSV, Excel (.xlsx), Word (.docx) or PDF file.");
  }
  const { api } = await import("@/lib/api");
  const fd = new FormData();
  fd.append("file", file);
  let data: { headers: string[]; rows: Record<string, string>[]; warnings?: string[] };
  try {
    ({ data } = await api.post("/imports/parse-file", fd, { headers: { "Content-Type": "multipart/form-data" } }));
  } catch (e: any) {
    throw new Error(e?.response?.data?.detail || "Could not read that file.");
  }
  const rows = data.rows || [];
  if (rows.length === 0) throw new Error("The file is empty or contains no valid rows.");
  if (rows.length > MAX_ROWS) throw new Error(`Too many rows. Maximum is ${MAX_ROWS.toLocaleString()} per file.`);
  return { headers: data.headers || [], rows, warnings: data.warnings || [] };
}

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
