import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow, format } from "date-fns";
import { env } from "@/lib/env";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function timeAgo(dateString: string | null): string {
  if (!dateString) return "Never";
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true });
  } catch {
    return "Unknown";
  }
}

export function formatDate(dateString: string | null, fmt = "MMM d, yyyy"): string {
  if (!dateString) return "—";
  try {
    return format(new Date(dateString), fmt);
  } catch {
    return "—";
  }
}

export function formatCurrency(amount: number, currency = "NGN"): string {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency }).format(amount);
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

// Uploaded media is served by the backend at /uploads/... (mounted via
// StaticFiles). Next.js only rewrites /api/v1/*, so a relative `/uploads`
// path resolves against the Next origin and 404s. Absolute URLs (S3, etc.)
// pass through unchanged — useful once we swap local storage for object
// storage.
export function resolveMediaUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  const base = env.NEXT_PUBLIC_API_URL.replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

export const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  inactive: "bg-slate-50 text-slate-600 border-slate-200",
  suspended: "bg-orange-50 text-orange-700 border-orange-200",
  pending: "bg-blue-50 text-blue-700 border-blue-200",
  locked: "bg-red-50 text-red-700 border-red-200",
};

export const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-500",
  warning: "bg-orange-500",
  critical: "bg-red-500",
};

// Coerce any axios/fetch error (or whatever the caller caught) into a string
// that's safe to render in a toast, alert, or JSX. This matters because FastAPI
// returns `detail` as an object on structured errors (plan limits, feature
// flags) and as an array of validation objects on 422s — passing either of
// those to React or toast directly triggers "Objects are not valid as a React
// child" crashes.
//
// Always returns a non-empty string.
export function getApiErrorMessage(
  error: unknown,
  fallback = "Something went wrong.",
): string {
  const anyErr = error as {
    response?: { data?: { detail?: unknown; message?: unknown; error?: unknown } };
    message?: unknown;
  } | null | undefined;
  const detail = anyErr?.response?.data?.detail;

  // FastAPI structured error: {error: "...", reason: "...", ...}
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === "string") return d.message;
    if (typeof d.reason === "string") return humanise(d.reason);
    if (typeof d.error === "string") return humanise(d.error);
  }

  // FastAPI validation 422: detail is an array of {loc, msg, type} objects.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown; loc?: unknown };
    if (typeof first?.msg === "string") {
      const loc = Array.isArray(first.loc) ? first.loc.filter((x) => typeof x === "string").join(".") : "";
      return loc ? `${loc}: ${first.msg}` : first.msg;
    }
  }

  if (typeof detail === "string" && detail.trim()) return detail;

  const message = anyErr?.response?.data?.message ?? anyErr?.message;
  if (typeof message === "string" && message.trim()) return message;

  return fallback;
}

function humanise(key: string): string {
  // Convert "plan_limit_exceeded" / "feature_disabled" into "Plan limit
  // exceeded" so a reason code coming back from the backend renders cleanly
  // when there's no human message attached.
  return key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}
