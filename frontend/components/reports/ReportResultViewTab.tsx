"use client";

import { useState } from "react";
import {
  useTerms, useSubTerms, useAssessments,
  useCumulatives, useCreateCumulative, useDeleteCumulative, useBootstrapCumulatives,
} from "@/hooks/usePlatform";
import { cn } from "@/lib/utils";
import { Plus, Trash2, Loader2, Sparkles, Layers } from "lucide-react";

type Sub = "cumulative" | "groupings" | "reorder" | "presentation" | "header";
const SUBS: [Sub, string, boolean][] = [
  ["cumulative", "Assessment Cumulative Setup", true],
  ["groupings", "Subject Groupings", false],
  ["reorder", "Subject ReOrder / Pass Mark", false],
  ["presentation", "Result Presentation Setup", false],
  ["header", "Result Header Setup", false],
];
const CUMUL_TYPES: [string, string][] = [["score", "Score (sum)"], ["percentage", "Percentage"], ["custom_percentage", "Custom %"]];

export function ResultViewTab({ canWrite }: { canWrite: boolean }) {
  const [sub, setSub] = useState<Sub>("cumulative");
  return (
    <div>
      <div className="inline-flex flex-wrap gap-1 bg-slate-100 rounded-lg p-1 mb-5">
        {SUBS.map(([k, l, live]) => (
          <button key={k} onClick={() => setSub(k)} className={cn("px-3 py-1.5 text-xs font-semibold rounded-md transition", sub === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700", !live && "opacity-60")}>{l}</button>
        ))}
      </div>
      {sub === "cumulative" ? <CumulativeSetup canWrite={canWrite} />
        : <div className="bg-white rounded-xl border border-dashed border-slate-200 p-12 text-center">
            <Layers size={30} className="mx-auto mb-3 text-slate-300" />
            <p className="text-sm font-semibold text-slate-600">{SUBS.find(([k]) => k === sub)?.[1]}</p>
            <p className="text-xs text-slate-400 mt-1">Not yet available — arrives in a later batch of the Secondary Report build-out.</p>
          </div>}
    </div>
  );
}

function CumulativeSetup({ canWrite }: { canWrite: boolean }) {
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const [termId, setTermId] = useState("");
  const { data: rows = [], isLoading } = useCumulatives(termId || undefined);
  const { data: assessments = [] } = useAssessments(termId || undefined);
  const create = useCreateCumulative();
  const del = useDeleteCumulative();
  const boot = useBootstrapCumulatives();

  const empty = { name: "", sub_term_id: "", cumul_type: "score", max_percent: "", components: [] as { ref_type: string; ref_id: string }[] };
  const [f, setF] = useState(empty);
  const toggleComp = (ref_type: string, ref_id: string) => setF((p) => {
    const on = p.components.some((c) => c.ref_id === ref_id && c.ref_type === ref_type);
    return { ...p, components: on ? p.components.filter((c) => !(c.ref_id === ref_id && c.ref_type === ref_type)) : [...p.components, { ref_type, ref_id }] };
  });
  const has = (ref_type: string, ref_id: string) => f.components.some((c) => c.ref_id === ref_id && c.ref_type === ref_type);

  const submit = () => {
    if (!termId || !f.name.trim() || !f.sub_term_id) return;
    create.mutate({
      name: f.name.trim(), term_id: termId, sub_term_id: f.sub_term_id, cumul_type: f.cumul_type,
      max_percent: f.cumul_type === "custom_percentage" && f.max_percent ? Number(f.max_percent) : null,
      components: f.components,
    }, { onSuccess: () => setF({ ...empty }) });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><label className="label">Term</label>
          <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input w-auto">
            <option value="">Select a term…</option>
            {(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        {canWrite && (terms as any[]).length > 0 && (
          <button onClick={() => boot.mutate({})} disabled={boot.isPending} className="btn-secondary gap-2">
            {boot.isPending ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Seed Fairview columns (Half-Term Total / % / CA1 / Total)
          </button>
        )}
      </div>
      <p className="text-xs text-slate-400">A cumulative is a report column built from assessments and/or other cumulatives. <b>Score</b> sums them; <b>Percentage</b> scales to 100; <b>Custom %</b> rescales to a chosen max.</p>

      {!termId ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">Select a term to view and build its cumulative columns.</p> : (
        <>
          {canWrite && (
            <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div><label className="label">Name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. TOTAL" /></div>
                <div><label className="label">Sub-term *</label><select value={f.sub_term_id} onChange={(e) => setF({ ...f, sub_term_id: e.target.value })} className="input"><option value="">—</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                <div><label className="label">Type</label><select value={f.cumul_type} onChange={(e) => setF({ ...f, cumul_type: e.target.value })} className="input">{CUMUL_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
                {f.cumul_type === "custom_percentage" && <div><label className="label">Max %</label><input type="number" value={f.max_percent} onChange={(e) => setF({ ...f, max_percent: e.target.value })} className="input" /></div>}
              </div>
              <div>
                <label className="label">Components</label>
                <div className="flex flex-wrap gap-1.5">
                  {(assessments as any[]).map((a) => <Chip key={"a" + a.id} on={has("assessment", a.id)} onClick={() => toggleComp("assessment", a.id)} label={a.name} kind="assessment" />)}
                  {(rows as any[]).map((c) => <Chip key={"c" + c.id} on={has("cumulative", c.id)} onClick={() => toggleComp("cumulative", c.id)} label={c.name} kind="cumulative" />)}
                </div>
                {(assessments as any[]).length === 0 && <p className="text-xs text-slate-400 mt-1">No assessments for this term yet — add them under the Assessment tab first.</p>}
              </div>
              <div className="flex justify-end"><button onClick={submit} disabled={!f.name.trim() || !f.sub_term_id || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Cumulative</button></div>
            </div>
          )}

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Name", "Type", "Max %", "Sub-term", "Components", ""].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? <tr><td colSpan={6} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
                  : (rows as any[]).length === 0 ? <tr><td colSpan={6} className="py-8 text-center text-sm text-slate-400">No cumulatives for this term. Use the Seed button for the standard columns.</td></tr>
                  : (rows as any[]).map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/70 align-top">
                      <td className="px-4 py-3 text-sm font-semibold text-slate-800">{c.name}</td>
                      <td className="px-4 py-3 text-sm text-slate-500 capitalize">{(c.cumul_type || "").replace("_", " ")}</td>
                      <td className="px-4 py-3 text-sm text-slate-500 tabular-nums">{c.max_percent != null ? Number(c.max_percent) : "—"}</td>
                      <td className="px-4 py-3 text-sm text-slate-500">{c.sub_term_name || "—"}</td>
                      <td className="px-4 py-3 text-xs text-slate-500 max-w-sm">{(c.components || []).map((k: any) => k.label || k.ref_id.slice(0, 6)).join(" + ") || "—"}</td>
                      <td className="px-4 py-3">{canWrite && <button onClick={() => del.mutate(c.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Chip({ on, onClick, label, kind }: { on: boolean; onClick: () => void; label: string; kind: string }) {
  return (
    <button type="button" onClick={onClick} className={cn("text-[11px] font-semibold px-2.5 py-1 rounded-full border transition",
      on ? (kind === "cumulative" ? "bg-brand-600 text-white border-brand-600" : "bg-emerald-600 text-white border-emerald-600")
         : "bg-white text-slate-500 border-slate-200 hover:border-slate-300")}>
      {kind === "cumulative" ? "Σ " : ""}{label}
    </button>
  );
}
