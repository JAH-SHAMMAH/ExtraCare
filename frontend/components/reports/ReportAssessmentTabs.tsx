"use client";

import { useState } from "react";
import {
  useTerms, useSubTerms,
  useAssessmentGroups, useCreateAssessmentGroup, useDeleteAssessmentGroup,
  useAssessments, useCreateAssessment, useDeleteAssessment, useBootstrapAssessments,
} from "@/hooks/usePlatform";
import { useYearGroups } from "@/hooks/useSchool";
import { Plus, Trash2, Loader2, Sparkles } from "lucide-react";

// ── Assessment Group ─────────────────────────────────────────────────────────

export function AssessmentGroupTab({ canWrite }: { canWrite: boolean }) {
  const { data: rows = [], isLoading } = useAssessmentGroups();
  const create = useCreateAssessmentGroup();
  const del = useDeleteAssessmentGroup();
  const [name, setName] = useState("");

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">Optional named buckets you can tag assessments with (e.g. a &ldquo;Continuous Assessment&rdquo; group).</p>
      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]"><label className="label">Group name</label><input value={name} onChange={(e) => setName(e.target.value)} className="input" placeholder="e.g. Continuous Assessment" /></div>
          <button onClick={() => name.trim() && create.mutate({ name: name.trim() }, { onSuccess: () => setName("") })} disabled={!name.trim() || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Assessment Group</button>
        </div>
      )}
      {isLoading ? <div className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        : (rows as any[]).length === 0 ? <p className="text-sm text-slate-400 py-6 text-center bg-white rounded-xl border border-slate-200">No assessment groups yet.</p>
        : (
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
            {(rows as any[]).map((g, i) => (
              <div key={g.id} className="flex items-center justify-between px-5 py-3">
                <span className="text-sm font-semibold text-slate-800">{i + 1}. {g.name}</span>
                {canWrite && <button onClick={() => { if (confirm("Delete " + g.name + "?")) del.mutate(g.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

// ── Assessment (leaf components) ─────────────────────────────────────────────

export function AssessmentTab({ canWrite }: { canWrite: boolean }) {
  const { data: terms = [] } = useTerms();
  const { data: subs = [] } = useSubTerms();
  const { data: years = [] } = useYearGroups();
  const { data: groups = [] } = useAssessmentGroups();
  const [termId, setTermId] = useState("");
  const { data: rows = [], isLoading } = useAssessments(termId || undefined);
  const create = useCreateAssessment();
  const del = useDeleteAssessment();
  const boot = useBootstrapAssessments();

  const empty = { name: "", code: "", term_id: "", sub_term_id: "", year_group: "", max_score: "", decimal_places: "0", group_id: "" };
  const [f, setF] = useState(empty);

  const submit = () => {
    if (!f.name.trim() || !f.term_id || !f.sub_term_id) return;
    create.mutate({
      name: f.name.trim(), code: f.code || null, term_id: f.term_id, sub_term_id: f.sub_term_id,
      year_group: f.year_group || null, max_score: f.max_score ? Number(f.max_score) : 100,
      decimal_places: Number(f.decimal_places || 0), group_id: f.group_id || null,
    }, { onSuccess: () => setF({ ...empty, term_id: f.term_id, sub_term_id: f.sub_term_id }) });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-end gap-3">
          <div><label className="label">Filter by term</label>
            <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input w-auto">
              <option value="">All terms</option>
              {(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>
        {canWrite && (terms as any[]).length > 0 && (
          <button onClick={() => boot.mutate({})} disabled={boot.isPending} className="btn-secondary gap-2">
            {boot.isPending ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />} Seed Fairview set (CBT/Theory/PRJ/PBT/EXAM)
          </button>
        )}
      </div>
      <p className="text-xs text-slate-400">Mark components scored out of a max, scoped to a term + sub-term and a level (blank = all levels). These feed the cumulative columns.</p>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <div><label className="label">Name *</label><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="input" placeholder="e.g. EXAM" /></div>
          <div><label className="label">Code</label><input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} className="input" placeholder="e.g. EXM" /></div>
          <div><label className="label">Max *</label><input type="number" value={f.max_score} onChange={(e) => setF({ ...f, max_score: e.target.value })} className="input" placeholder="e.g. 60" /></div>
          <div><label className="label">Decimals</label><input type="number" value={f.decimal_places} onChange={(e) => setF({ ...f, decimal_places: e.target.value })} className="input" /></div>
          <div><label className="label">Term *</label><select value={f.term_id} onChange={(e) => setF({ ...f, term_id: e.target.value })} className="input"><option value="">—</option>{(terms as any[]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
          <div><label className="label">Sub-term *</label><select value={f.sub_term_id} onChange={(e) => setF({ ...f, sub_term_id: e.target.value })} className="input"><option value="">—</option>{(subs as any[]).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <div><label className="label">Level</label><select value={f.year_group} onChange={(e) => setF({ ...f, year_group: e.target.value })} className="input"><option value="">All Levels</option>{(years as any[]).map((y) => <option key={y.id || y.name} value={y.name}>{y.name}</option>)}</select></div>
          <div><label className="label">Group</label><select value={f.group_id} onChange={(e) => setF({ ...f, group_id: e.target.value })} className="input"><option value="">—</option>{(groups as any[]).map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
          <div className="col-span-2 md:col-span-4 flex justify-end"><button onClick={submit} disabled={!f.name.trim() || !f.term_id || !f.sub_term_id || create.isPending} className="btn-primary gap-2"><Plus size={15} /> Add Assessment</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Name", "Code", "Max", "Term", "Sub-term", "Level", "Dec.", ""].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={8} className="py-10 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></td></tr>
              : (rows as any[]).length === 0 ? <tr><td colSpan={8} className="py-8 text-center text-sm text-slate-400">No assessments{termId ? " for this term" : ""}. Use the Seed button for the standard set.</td></tr>
              : (rows as any[]).map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{a.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{a.code || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-700 tabular-nums">{Number(a.max_score)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{a.term_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{a.sub_term_name || "—"}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{a.year_group || "All Levels"}</td>
                  <td className="px-4 py-3 text-sm text-slate-500 tabular-nums">{a.decimal_places}</td>
                  <td className="px-4 py-3">{canWrite && <button onClick={() => del.mutate(a.id)} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={15} /></button>}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
