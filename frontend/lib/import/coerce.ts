// Shared coercion helpers used by ImportColumn.transform.
//
// Design note on empty values:
//   The canonical Zod schemas in lib/validations.ts use two shapes for optional
//   string fields:
//     1. `z.string().email().or(z.literal(""))`  — accepts "" but NOT undefined
//     2. `z.string().optional().or(z.literal(""))` — accepts either
//     3. `z.enum([...]).optional()` — accepts undefined, NOT ""
//
//   To stay compatible with (1), string-typed transforms must return "" for
//   empty values (not undefined). Enum/date transforms return undefined since
//   their schemas allow it and the enum cannot accept "".

/** Trim whitespace. Returns "" for empty strings (stays compatible with `.or(z.literal(""))`). */
export function trimString(v: unknown): unknown {
  if (typeof v !== "string") return v;
  return v.trim();
}

/** Lowercase + trim. Use for emails. Returns "" for empty. */
export function toLowerTrim(v: unknown): unknown {
  if (typeof v !== "string") return v;
  return v.trim().toLowerCase();
}

/**
 * Gender coercion. Accepts: "Male", "MALE", "M", "m", "Female", "F", "Other", "O".
 * Returns canonical lowercase enum value, undefined for empty, or the original
 * (to let Zod surface a helpful mismatch error).
 */
export function coerceGender(v: unknown): unknown {
  if (typeof v !== "string") return v;
  const t = v.trim().toLowerCase();
  if (t === "") return undefined;
  if (t === "m" || t === "male") return "male";
  if (t === "f" || t === "female") return "female";
  if (t === "o" || t === "other") return "other";
  return t;
}

/**
 * Normalizes a date string to ISO `YYYY-MM-DD`.
 * Accepts: "2010-05-14", "14/05/2010", "14-05-2010", "05/14/2010", "14.05.2010",
 * "2010/05/14". Ambiguous DD/MM vs MM/DD defaults to DD/MM (dominant in
 * Africa/Europe). Returns undefined for empty, the original string on failure
 * so Zod surfaces a meaningful error.
 */
export function coerceDate(v: unknown): unknown {
  if (typeof v !== "string") return v;
  const s = v.trim();
  if (s === "") return undefined;

  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  const parts = s.split(/[\/\-.]/).map((p) => p.trim());
  if (parts.length !== 3) return s;

  let year: string, month: string, day: string;

  if (parts[0].length === 4) {
    [year, month, day] = parts;
  } else if (parts[2].length === 4) {
    year = parts[2];
    const a = parseInt(parts[0], 10);
    const b = parseInt(parts[1], 10);
    if (a > 12) { day = parts[0]; month = parts[1]; }
    else if (b > 12) { month = parts[0]; day = parts[1]; }
    else { day = parts[0]; month = parts[1]; }
  } else {
    return s;
  }

  const y = parseInt(year, 10);
  const m = parseInt(month, 10);
  const d = parseInt(day, 10);
  if (isNaN(y) || isNaN(m) || isNaN(d)) return s;
  if (m < 1 || m > 12 || d < 1 || d > 31 || y < 1900 || y > 2100) return s;

  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}
