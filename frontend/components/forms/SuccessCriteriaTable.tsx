"use client";

import { useState, useEffect } from "react";
import { Plus, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import DOMPurify from "dompurify";

interface SuccessCriteriaRow {
  id: string;
  criteria: string;
  some: boolean;
  most: boolean;
  all: boolean;
}

interface SuccessCriteriaData {
  rows: SuccessCriteriaRow[];
}

/**
 * Success Criteria table component — 4-column matrix (Criteria, Some, Most, All).
 * Each row allows a text description + 3 achievement-level checkboxes.
 * Stores/loads as JSON in a Text field: {"rows": [...]}
 */
export function SuccessCriteriaTable({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (v: string) => void;
}) {
  const [rows, setRows] = useState<SuccessCriteriaRow[]>([]);

  // Parse JSON from value on mount/change
  useEffect(() => {
    if (!value || value.trim() === "") {
      setRows([]);
      return;
    }
    try {
      const parsed: SuccessCriteriaData = JSON.parse(value);
      setRows(Array.isArray(parsed?.rows) ? parsed.rows : []);
    } catch {
      setRows([]);
    }
  }, [value]);

  // Serialize rows to JSON and call onChange
  const updateRows = (newRows: SuccessCriteriaRow[]) => {
    setRows(newRows);
    const serialized = JSON.stringify({
      rows: newRows.map((r) => ({
        id: r.id,
        criteria: DOMPurify.sanitize(r.criteria, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] }),
        some: r.some,
        most: r.most,
        all: r.all,
      })),
    });
    onChange(serialized);
  };

  const addRow = () => {
    const newRow: SuccessCriteriaRow = {
      id: crypto.getRandomUUID(),
      criteria: "",
      some: false,
      most: false,
      all: false,
    };
    updateRows([...rows, newRow]);
  };

  const updateCriteria = (id: string, criteria: string) => {
    updateRows(
      rows.map((r) => (r.id === id ? { ...r, criteria } : r)),
    );
  };

  const toggleCheckbox = (id: string, level: "some" | "most" | "all") => {
    updateRows(
      rows.map((r) =>
        r.id === id ? { ...r, [level]: !r[level] } : r,
      ),
    );
  };

  const deleteRow = (id: string) => {
    updateRows(rows.filter((r) => r.id !== id));
  };

  return (
    <div>
      <label className="label">Success Criteria</label>
      <div className="border border-slate-200 rounded-lg overflow-hidden bg-white">
        {rows.length === 0 ? (
          <div className="p-6 text-center">
            <p className="text-sm text-slate-500 mb-3">No success criteria yet.</p>
            <button
              type="button"
              onClick={addRow}
              className="btn-secondary gap-2 text-sm"
            >
              <Plus size={14} />
              Add your first criterion
            </button>
          </div>
        ) : (
          <>
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-4 py-3 text-left text-xs font-bold uppercase tracking-widest text-slate-600 w-1/2">
                    Criterion
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-bold uppercase tracking-widest text-slate-600 w-1/6">
                    Some
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-bold uppercase tracking-widest text-slate-600 w-1/6">
                    Most
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-bold uppercase tracking-widest text-slate-600 w-1/6">
                    All
                  </th>
                  <th className="px-4 py-3 w-12" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {rows.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3">
                      <input
                        type="text"
                        value={row.criteria}
                        onChange={(e) => updateCriteria(row.id, e.target.value)}
                        placeholder="e.g., Can identify key themes"
                        className="input text-sm w-full"
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      <label className="inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={row.some}
                          onChange={() => toggleCheckbox(row.id, "some")}
                          className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                        />
                      </label>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <label className="inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={row.most}
                          onChange={() => toggleCheckbox(row.id, "most")}
                          className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                        />
                      </label>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <label className="inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={row.all}
                          onChange={() => toggleCheckbox(row.id, "all")}
                          className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                        />
                      </label>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        type="button"
                        onClick={() => deleteRow(row.id)}
                        className="p-2 rounded hover:bg-red-50 text-slate-400 hover:text-red-600 transition-colors"
                        title="Delete row"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="bg-slate-50 border-t border-slate-200 px-4 py-3">
              <button
                type="button"
                onClick={addRow}
                className="text-sm font-semibold text-slate-600 hover:text-brand-700 flex items-center gap-1.5"
              >
                <Plus size={14} />
                Add row
              </button>
            </div>
          </>
        )}
      </div>
      <p className="text-xs text-slate-500 mt-2">
        Check the boxes to indicate what level of success each criterion demonstrates (Some/Most/All).
      </p>
    </div>
  );
}
