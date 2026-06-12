const STORAGE_KEY = "extracare-import-history";
const MAX_ENTRIES = 20;

export interface ImportHistoryEntry {
  id: string;
  entity: string;
  filename: string;
  timestamp: string; // ISO
  totalRows: number;
  validRows: number;
  created: number;
  failed: number;
  skippedInvalid: number;
  durationMs: number;
}

export function getImportHistory(): ImportHistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function addImportEntry(entry: Omit<ImportHistoryEntry, "id" | "timestamp">): ImportHistoryEntry {
  const full: ImportHistoryEntry = {
    ...entry,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
  };
  const history = getImportHistory();
  history.unshift(full);
  // Keep only the most recent entries
  const trimmed = history.slice(0, MAX_ENTRIES);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // storage full — silently fail
  }
  return full;
}

export function clearImportHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY);
}
