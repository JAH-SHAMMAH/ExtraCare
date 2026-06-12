import type { ImportPreset } from "./presets";

/**
 * Builds a template CSV string for a given preset: header row plus two example
 * rows derived from each column's `example` field.
 */
export function buildTemplateCSV<T>(preset: ImportPreset<T>): string {
  const headers = preset.columns.map((c) => c.label);
  const example1 = preset.columns.map((c) => c.example);
  const example2 = preset.columns.map((c) => c.example ? c.example.toUpperCase().slice(0, 1) + c.example.slice(1) : "");

  const escape = (v: string) => `"${String(v).replace(/"/g, '""')}"`;
  return [headers, example1, example2].map((row) => row.map(escape).join(",")).join("\n");
}

export function downloadCSV(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
