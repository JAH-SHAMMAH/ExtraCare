"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, X, Loader2, ChevronDown } from "lucide-react";
import { schoolApi, messengerApi } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Reusable type-ahead picker that searches people/records by name and returns
 * the selected id. Shared infrastructure for every batch that links a person —
 * no more raw-id entry. Backed by EXISTING search endpoints (no new ones):
 *   • student        → GET /school/students?search=  (school:students:read)
 *   • parent / staff → GET /messenger/contacts?search= (auth-only user search)
 *
 * Controlled: the parent owns `value` (the id). `valueLabel` lets a parent seed
 * the display text when editing an existing record.
 *
 * ⚠️ GOTCHA — DO NOT wrap this picker in a container with `overflow-hidden`
 * (nor `overflow-y-auto`/`overflow-auto`, which CSS resolves overflow-x to `auto`
 * too). The results dropdown is absolutely-positioned and extends BELOW the input,
 * so any clipping ancestor makes it render invisible/cut-off — the field then
 * looks "empty / broken" even though search is returning results. In particular,
 * never place it inside a `<table>`/`<td>` results wrapper (those use
 * `overflow-hidden`). Use a plain `<div>` or a CSS grid cell instead — see the
 * Payroll / Salary Advance / Bonus-Reduction create forms for the correct pattern.
 * (This bit us once in Bonus/Reduction Pack — the picker was in an `overflow-hidden`
 * table wrapper and appeared empty for all users.)
 */
export type EntityType = "student" | "parent" | "staff";

export interface EntityOption {
  id: string;
  label: string;
  sub?: string | null;
}

const PLACEHOLDERS: Record<EntityType, string> = {
  student: "Search students by name or ID…",
  parent: "Search parents by name or email…",
  staff: "Search staff by name or email…",
};

async function searchEntities(type: EntityType, term: string): Promise<EntityOption[]> {
  const q = term.trim() || undefined;
  if (type === "student") {
    const res = await schoolApi.students.list({ search: q, page_size: 10 });
    const items = (res?.items ?? []) as any[];
    return items.map((s) => ({
      id: s.id,
      label: [s.first_name, s.last_name].filter(Boolean).join(" ") || s.student_id || s.id,
      sub: s.student_id || s.email || null,
    }));
  }
  // parent + staff are both User rows — reuse the auth-only contacts search so
  // every staff role can resolve a person without the admin-only users:read.
  const rows = (await messengerApi.contacts.list({ search: q, limit: 10 })) as any[];
  return rows.map((u) => ({ id: u.id, label: u.full_name, sub: u.email }));
}

export function EntityPicker({
  type, value, valueLabel, onChange, disabled, placeholder, id,
}: {
  type: EntityType;
  value: string | null;
  valueLabel?: string | null;
  onChange: (id: string | null, label?: string) => void;
  disabled?: boolean;
  placeholder?: string;
  id?: string;
}) {
  const [open, setOpen] = useState(false);
  const [term, setTerm] = useState("");
  const [debounced, setDebounced] = useState("");
  const [label, setLabel] = useState<string | null>(valueLabel ?? null);
  const boxRef = useRef<HTMLDivElement>(null);

  // Keep the displayed label in sync when the parent seeds/clears it.
  useEffect(() => { setLabel(valueLabel ?? null); }, [valueLabel]);

  // Debounce typing so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setDebounced(term), 250);
    return () => clearTimeout(t);
  }, [term]);

  // Close the dropdown on outside click.
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const { data: options = [], isFetching } = useQuery({
    queryKey: ["entity-search", type, debounced],
    queryFn: () => searchEntities(type, debounced),
    enabled: open && !disabled,
    staleTime: 15_000,
  });

  const pick = (opt: EntityOption) => {
    setLabel(opt.label);
    onChange(opt.id, opt.label);
    setOpen(false);
    setTerm("");
  };

  const clear = () => {
    setLabel(null);
    onChange(null);
    setTerm("");
    setOpen(false);
  };

  // Selected state: show a chip with the chosen person + change/clear controls.
  if (value && !open) {
    return (
      <div ref={boxRef} className="flex items-center justify-between gap-2 rounded-md border border-slate-300 bg-white px-3 py-2">
        <span className="text-sm text-slate-800 truncate">{label || value}</span>
        {!disabled && (
          <div className="flex items-center gap-1 shrink-0">
            <button type="button" onClick={() => setOpen(true)} className="text-xs font-semibold text-brand-600 hover:text-brand-700">Change</button>
            <button type="button" onClick={clear} className="text-slate-400 hover:text-red-600 p-0.5" title="Clear"><X size={14} /></button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={boxRef} className="relative">
      <div className="relative">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          id={id}
          value={term}
          disabled={disabled}
          onChange={(e) => { setTerm(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder || PLACEHOLDERS[type]}
          className="input pl-9 pr-8"
          autoComplete="off"
        />
        {isFetching
          ? <Loader2 size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 animate-spin" />
          : <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />}
      </div>

      {open && !disabled && (
        <div className="absolute z-20 mt-1 w-full bg-white rounded-lg border border-slate-200 shadow-lg max-h-64 overflow-y-auto">
          {isFetching && options.length === 0 ? (
            <p className="px-3 py-3 text-xs text-slate-400">Searching…</p>
          ) : options.length === 0 ? (
            <p className="px-3 py-3 text-xs text-slate-400">
              {debounced.trim() ? "No matches." : "Type to search…"}
            </p>
          ) : (
            <ul className="py-1">
              {options.map((opt) => (
                <li key={opt.id}>
                  <button
                    type="button"
                    onClick={() => pick(opt)}
                    className={cn(
                      "w-full text-left px-3 py-2 hover:bg-slate-50 transition",
                      opt.id === value && "bg-brand-50",
                    )}
                  >
                    <p className="text-sm font-medium text-slate-800 truncate">{opt.label}</p>
                    {opt.sub && <p className="text-xs text-slate-400 truncate">{opt.sub}</p>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
