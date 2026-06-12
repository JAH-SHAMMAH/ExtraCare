import { z } from "zod";
import { studentSchema } from "@/lib/validations";
import { schoolApi } from "@/lib/api";
import { coerceDate, coerceGender, toLowerTrim, trimString } from "./coerce";

// ── Types ───────────────────────────────────────────────────────────────────

export interface ImportColumn<T> {
  key: keyof T & string;
  label: string;
  required: boolean;
  example: string;
  /** Alternative header names we auto-match against (lowercased, punctuation-stripped) */
  aliases?: string[];
  /**
   * Per-column value coercion applied BEFORE Zod validation. Lets us normalize
   * real-world CSV variants (Title Case, DD/MM/YYYY, "M"/"F") without touching
   * the canonical schemas used by the interactive forms.
   */
  transform?: (value: unknown) => unknown;
}

export interface BulkCommitProgress {
  processed: number;
  total: number;
}

export interface BulkCommitResult {
  created: number;
  failed: Array<{ row: number; error: string; data: unknown }>;
  /** IDs of successfully created records — used for bulk undo */
  createdIds: string[];
}

export interface ImportPreset<T> {
  entity: string;
  label: string;
  description: string;
  schema: z.ZodSchema<T>;
  columns: ImportColumn<T>[];
  listRoute: string;
  bulkCreate: (rows: T[], onProgress: (p: BulkCommitProgress) => void) => Promise<BulkCommitResult>;
}

// ── Error extraction (FastAPI / Pydantic aware) ─────────────────────────────

/**
 * FastAPI returns errors in multiple shapes:
 *  - Plain 500: { detail: "Something broke" }
 *  - HTTPException(422, "Email exists"): { detail: "Email exists" }
 *  - Pydantic validation: { detail: [{ loc: ["body","email"], msg: "...", type: "..." }] }
 *  - Custom: { detail: { message: "...", code: "..." } }
 *  - Network/timeout: Axios error with no response
 *
 * This extractor handles all of the above and always returns a human-readable
 * single-line string suitable for the failures table.
 */
export function extractErrorMessage(err: unknown): string {
  // Axios error shape
  const axiosErr = err as {
    response?: { data?: unknown; status?: number; statusText?: string };
    message?: string;
    code?: string;
  };

  // No response → network/timeout
  if (!axiosErr.response) {
    if (axiosErr.code === "ECONNABORTED") return "Request timed out";
    if (axiosErr.code === "ERR_NETWORK") return "Network error — check connection";
    return axiosErr.message || "Unknown error";
  }

  const data = axiosErr.response.data;
  const status = axiosErr.response.status;

  // String detail
  if (typeof data === "string") return data;
  if (data && typeof data === "object") {
    const detail = (data as { detail?: unknown; message?: unknown; error?: unknown }).detail
      ?? (data as { message?: unknown }).message
      ?? (data as { error?: unknown }).error;

    if (typeof detail === "string") return detail;

    // Pydantic validation array
    if (Array.isArray(detail)) {
      const messages = detail.map((d) => {
        if (typeof d === "string") return d;
        if (d && typeof d === "object") {
          const item = d as { loc?: unknown[]; msg?: string; message?: string };
          const field = Array.isArray(item.loc)
            ? item.loc.filter((p) => p !== "body").join(".")
            : "";
          const msg = item.msg || item.message || "Validation error";
          return field ? `${field}: ${msg}` : msg;
        }
        return String(d);
      });
      return messages.join("; ");
    }

    // Nested object (e.g. { detail: { message, code } })
    if (detail && typeof detail === "object") {
      const nested = detail as { message?: string; msg?: string };
      if (nested.message) return nested.message;
      if (nested.msg) return nested.msg;
      return JSON.stringify(detail);
    }
  }

  // Fallback to HTTP status
  if (status) return `HTTP ${status}${axiosErr.response.statusText ? `: ${axiosErr.response.statusText}` : ""}`;
  return axiosErr.message || "Unknown error";
}

// ── Shared batched create ───────────────────────────────────────────────────

const BATCH_SIZE = 10;

async function batchedCreate<T>(
  rows: T[],
  createFn: (row: T) => Promise<unknown>,
  onProgress: (p: BulkCommitProgress) => void
): Promise<BulkCommitResult> {
  const result: BulkCommitResult = { created: 0, failed: [], createdIds: [] };
  let processed = 0;

  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE);
    const outcomes = await Promise.allSettled(batch.map((row) => createFn(row)));
    outcomes.forEach((outcome, j) => {
      if (outcome.status === "fulfilled") {
        result.created++;
        // Extract ID from the created record for undo support
        const record = outcome.value as { id?: string } | undefined;
        if (record?.id) result.createdIds.push(record.id);
      } else {
        result.failed.push({
          row: i + j + 1,
          error: extractErrorMessage(outcome.reason),
          data: batch[j],
        });
      }
      processed++;
      onProgress({ processed, total: rows.length });
    });
  }

  return result;
}

// ── Student Preset ──────────────────────────────────────────────────────────

type StudentRow = z.infer<typeof studentSchema>;

export const studentImportPreset: ImportPreset<StudentRow> = {
  entity: "students",
  label: "Import Students",
  description: "Upload a CSV file to bulk-add students to your school.",
  schema: studentSchema,
  listRoute: "/dashboard/modules/school/students",
  columns: [
    {
      key: "first_name",
      label: "First Name",
      required: true,
      example: "Ada",
      aliases: ["firstname", "first", "fname", "given name", "given"],
      transform: trimString,
    },
    {
      key: "last_name",
      label: "Last Name",
      required: true,
      example: "Okonkwo",
      aliases: ["lastname", "last", "lname", "surname", "family name"],
      transform: trimString,
    },
    {
      key: "email",
      label: "Email",
      required: false,
      example: "ada.okonkwo@example.com",
      aliases: ["email address", "e-mail"],
      transform: toLowerTrim,
    },
    {
      key: "phone",
      label: "Phone",
      required: false,
      example: "+2348012345678",
      aliases: ["phone number", "mobile", "tel", "telephone"],
      transform: trimString,
    },
    {
      key: "date_of_birth",
      label: "Date of Birth",
      required: false,
      example: "2010-05-14",
      aliases: ["dob", "birth date", "birthdate", "born"],
      transform: coerceDate,
    },
    {
      key: "gender",
      label: "Gender",
      required: false,
      example: "female",
      aliases: ["sex"],
      transform: coerceGender,
    },
    {
      key: "guardian_name",
      label: "Guardian Name",
      required: false,
      example: "Mrs. Chioma Okonkwo",
      aliases: ["parent", "parent name", "guardian"],
      transform: trimString,
    },
    {
      key: "guardian_phone",
      label: "Guardian Phone",
      required: false,
      example: "+2348098765432",
      aliases: ["parent phone", "guardian contact", "parent contact"],
      transform: trimString,
    },
    {
      key: "address",
      label: "Address",
      required: false,
      example: "14 Lagos Street, Ikeja",
      aliases: ["home address", "residence"],
      transform: trimString,
    },
    {
      key: "class_id",
      label: "Class ID",
      required: false,
      example: "",
      aliases: ["class", "class code", "grade"],
      transform: trimString,
    },
  ],
  bulkCreate: (rows, onProgress) =>
    batchedCreate(rows, (row) => schoolApi.students.create(row as unknown as object), onProgress),
};
