"use client";

import { Plus, Trash2 } from "lucide-react";
import type { PatternDef, PatternItem } from "@/lib/api";
import { PATTERN_TYPES, previewPattern } from "@/lib/pattern";
import { Panel, SaveBar, useStructEditor } from "@/components/super/shared";

const NAME_TYPES = ["first_name", "surname", "other_name"];

/** Builder for one pattern (Reg. number, Staff ID, Email, Student email): items + separator + suffix, with a live example. */
export function PatternTab({ title, patternKey, server, lower = false }: {
  title: string; patternKey: string; server: Record<string, PatternDef> | undefined; lower?: boolean;
}) {
  const { value, edit, commit, dirty, saving } = useStructEditor<Record<string, PatternDef>>("patterns", server);
  const pat = value?.[patternKey];
  if (!value || !pat) return null;
  const set = (p: PatternDef) => edit({ ...value, [patternKey]: p });
  const setItem = (i: number, it: Partial<PatternItem>) => set({ ...pat, items: pat.items.map((x, j) => (j === i ? { ...x, ...it } : x)) });
  return (
    <Panel title={title}>
      <p className="text-sm text-slate-500 mb-1">Example</p>
      <p className="text-lg font-bold break-all mb-4 border-l-4 border-sky-500 bg-sky-50 px-3 py-2" data-testid="pattern-preview">{previewPattern(pat, lower)}</p>
      <div className="space-y-2">
        {pat.items.map((it, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2 border border-slate-200 rounded-lg p-2">
            <span className="w-6 text-slate-400 text-sm">{i + 1}</span>
            <select className="input w-44" aria-label={`Item ${i + 1} type`} value={it.type} onChange={(e) => setItem(i, { type: e.target.value, length: e.target.value === "sequence" ? 4 : "full", text: "" })}>
              {PATTERN_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            {NAME_TYPES.includes(it.type) && (
              <select className="input w-40" aria-label={`Item ${i + 1} length`} value={it.length === "full" || !it.length ? "full" : String(it.length)} onChange={(e) => setItem(i, { length: e.target.value === "full" ? "full" : Number(e.target.value) })}>
                <option value="full">Full</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>First {n} letter{n > 1 ? "s" : ""}</option>)}
              </select>
            )}
            {it.type === "text" && <input className="input w-40" aria-label={`Item ${i + 1} text`} value={it.text ?? ""} maxLength={40} onChange={(e) => setItem(i, { text: e.target.value })} />}
            {it.type === "sequence" && (
              <select className="input w-40" aria-label={`Item ${i + 1} digits`} value={Number(it.length) || 4} onChange={(e) => setItem(i, { length: Number(e.target.value) })}>
                {[2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n} digits</option>)}
              </select>
            )}
            <button onClick={() => pat.items.length > 1 && set({ ...pat, items: pat.items.filter((_, j) => j !== i) })} aria-label={`Remove item ${i + 1}`} className="ml-auto text-red-500 p-1"><Trash2 size={16} /></button>
          </div>
        ))}
      </div>
      <button onClick={() => pat.items.length < 12 && set({ ...pat, items: [...pat.items, { type: "text", length: "full", text: "" }] })} className="btn-secondary gap-1 mt-3"><Plus size={15} /> Add item</button>
      <div className="grid sm:grid-cols-2 gap-3 mt-4">
        <div><label className="label">Separator between items</label><input className="input" maxLength={3} value={pat.separator} onChange={(e) => set({ ...pat, separator: e.target.value })} /></div>
        <div><label className="label">Ending (e.g. @school.com)</label><input className="input" value={pat.suffix} onChange={(e) => set({ ...pat, suffix: e.target.value })} /></div>
      </div>
      <SaveBar dirty={dirty} saving={saving} onSave={commit} label="Save Pattern" />
    </Panel>
  );
}
