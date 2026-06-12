import { z } from "zod";
import { getFormErrors } from "@/lib/validations";
import type { ImportColumn } from "./presets";

export interface ValidRow<T> {
  /** 1-indexed row number in the source file (header is row 1, data starts at row 2) */
  rowNumber: number;
  data: T;
}

export interface InvalidRow {
  rowNumber: number;
  raw: Record<string, unknown>;
  errors: Record<string, string>;
}

export interface DuplicateInfo {
  rowNumber: number;
  field: string;
  value: string;
}

export interface ValidationResult<T> {
  valid: ValidRow<T>[];
  invalid: InvalidRow[];
  /**
   * In-file duplicates. The FIRST occurrence stays in `valid`; subsequent
   * occurrences are moved OUT of valid into this list so we never commit them.
   */
  duplicates: DuplicateInfo[];
}

function projectRow<T>(
  raw: Record<string, string>,
  mapping: Record<string, string>,
  columns: ImportColumn<T>[]
): Record<string, unknown> {
  const projected: Record<string, unknown> = {};
  for (const col of columns) {
    const sourceHeader = mapping[col.key];
    // Unmapped columns get an empty string (not undefined). This matters for
    // schema fields shaped as `.or(z.literal(""))` without `.optional()`, like
    // emailField and phoneField — they reject undefined but accept "".
    // Transforms normalize "" correctly: trimString("") = "",
    // coerceGender("") = undefined (enum is optional so OK),
    // coerceDate("") = undefined (optionalDate accepts).
    const rawValue = sourceHeader ? (raw[sourceHeader] ?? "") : "";
    projected[col.key] = col.transform ? col.transform(rawValue) : rawValue;
  }
  return projected;
}

/**
 * Synchronous validation. Fine for files up to ~1k rows. For larger files use
 * validateRowsAsync which yields to the event loop every chunk.
 */
export function validateRows<T>(
  schema: z.ZodSchema<T>,
  rawRows: Record<string, string>[],
  mapping: Record<string, string>,
  columns: ImportColumn<T>[]
): ValidationResult<T> {
  const valid: ValidRow<T>[] = [];
  const invalid: InvalidRow[] = [];
  const duplicates: DuplicateInfo[] = [];
  const seenEmails = new Set<string>();

  rawRows.forEach((raw, idx) => {
    const rowNumber = idx + 2;
    const projected = projectRow(raw, mapping, columns);
    const parsed = schema.safeParse(projected);

    if (!parsed.success) {
      invalid.push({ rowNumber, raw: projected, errors: getFormErrors(parsed) });
      return;
    }

    // In-file duplicate check on email. First occurrence wins; later ones are
    // filtered out of valid[] entirely so they never reach the backend.
    const email = (projected.email as string | undefined)?.toLowerCase();
    if (email) {
      if (seenEmails.has(email)) {
        duplicates.push({ rowNumber, field: "email", value: email });
        return; // skip — don't push to valid
      }
      seenEmails.add(email);
    }

    valid.push({ rowNumber, data: parsed.data });
  });

  return { valid, invalid, duplicates };
}

/**
 * Async chunked validation. Processes rows in chunks of CHUNK_SIZE, yielding
 * to the event loop between chunks so the UI stays responsive and progress
 * callbacks fire. Use for files > 1,000 rows.
 */
export async function validateRowsAsync<T>(
  schema: z.ZodSchema<T>,
  rawRows: Record<string, string>[],
  mapping: Record<string, string>,
  columns: ImportColumn<T>[],
  onProgress?: (processed: number, total: number) => void
): Promise<ValidationResult<T>> {
  const CHUNK_SIZE = 200;
  const valid: ValidRow<T>[] = [];
  const invalid: InvalidRow[] = [];
  const duplicates: DuplicateInfo[] = [];
  const seenEmails = new Set<string>();

  for (let start = 0; start < rawRows.length; start += CHUNK_SIZE) {
    const end = Math.min(start + CHUNK_SIZE, rawRows.length);
    for (let i = start; i < end; i++) {
      const rowNumber = i + 2;
      const projected = projectRow(rawRows[i], mapping, columns);
      const parsed = schema.safeParse(projected);

      if (!parsed.success) {
        invalid.push({ rowNumber, raw: projected, errors: getFormErrors(parsed) });
        continue;
      }

      const email = (projected.email as string | undefined)?.toLowerCase();
      if (email) {
        if (seenEmails.has(email)) {
          duplicates.push({ rowNumber, field: "email", value: email });
          continue;
        }
        seenEmails.add(email);
      }
      valid.push({ rowNumber, data: parsed.data });
    }
    onProgress?.(end, rawRows.length);
    // Yield to event loop so UI paints
    await new Promise((r) => setTimeout(r, 0));
  }

  return { valid, invalid, duplicates };
}

/** Auto-match source headers to schema columns. Returns schemaField → sourceHeader. */
export function autoMapHeaders<T>(
  sourceHeaders: string[],
  columns: ImportColumn<T>[]
): Record<string, string> {
  const normalize = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");
  const normalizedSources = sourceHeaders.map((h) => ({ original: h, normalized: normalize(h) }));
  const mapping: Record<string, string> = {};

  for (const col of columns) {
    const candidates = [col.key, col.label, ...(col.aliases || [])].map(normalize);
    const match = normalizedSources.find((h) => candidates.includes(h.normalized));
    if (match) mapping[col.key] = match.original;
  }

  return mapping;
}

/** Builds a downloadable errors CSV. */
export function buildErrorsCSV(invalid: InvalidRow[]): string {
  const header = ["row", "field", "error", "value"].join(",");
  const lines = invalid.flatMap((row) =>
    Object.entries(row.errors).map(([field, error]) => {
      const value = String(row.raw[field] ?? "");
      return [row.rowNumber, field, error, value]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",");
    })
  );
  return [header, ...lines].join("\n");
}
