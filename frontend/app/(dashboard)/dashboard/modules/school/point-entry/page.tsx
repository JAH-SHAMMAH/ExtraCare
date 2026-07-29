"use client";

import { useMemo, useState } from "react";
import { usePastoralStudents, usePointTypes, useAddPoint, usePointEntries } from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Loader2, PlusCircle, Award } from "lucide-react";

const TERMS = ["Opening", "Autumn Term", "Spring Term", "Summer Term"];

export default function PointEntryPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const [search, setSearch] = useState("");
  const { data: roster = [] } = usePastoralStudents(search ? { search } : undefined);
  const { data: pointTypes = [] } = usePointTypes();
  const { data: recent = [] } = usePointEntries();
  const add = useAddPoint();

  const [f, setF] = useState({ student_id: "", type_name: "", points: "", term: "Autumn Term", reason: "" });
  const activeTypes = useMemo(() => (pointTypes as any[]).filter((t) => t.is_active), [pointTypes]);
  const selType = activeTypes.find((t) => t.name === f.type_name);

  const submit = () => {
    if (!f.student_id || !f.points) return;
    add.mutate(
      {
        student_id: f.student_id,
        points: Number(f.points),
        term: f.term,
        category: selType?.category || null,
        title: f.type_name || null,
        reason: f.reason || null,
      },
      { onSuccess: () => setF((p) => ({ ...p, points: "", reason: "" })) },
    );
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Point Entry</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><PlusCircle size={22} className="text-brand-600" /> Point Entry</h1>
      <p className="text-slate-500 text-sm mb-5">Award merits or record demerits against a student. Use a negative value for a demerit.</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {canWrite ? (
          <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div>
              <label className="label">Find student</label>
              <input value={search} onChange={(e) => setSearch(e.target.value)} className="input" placeholder="Search name…" />
            </div>
            <div>
              <label className="label">Student</label>
              <select value={f.student_id} onChange={(e) => setF({ ...f, student_id: e.target.value })} className="input">
                <option value="">— Select —</option>
                {(roster as any[]).map((r) => <option key={r.student_id} value={r.student_id}>{r.student_name}{r.house_name ? ` · ${r.house_name}` : ""}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Point type</label>
                <select value={f.type_name} onChange={(e) => setF({ ...f, type_name: e.target.value })} className="input">
                  <option value="">— None —</option>
                  {activeTypes.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Term</label>
                <select value={f.term} onChange={(e) => setF({ ...f, term: e.target.value })} className="input">
                  {TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="label">Points {selType?.max_point ? <span className="text-slate-400 font-normal">(max {selType.max_point})</span> : null}</label>
              <input type="number" value={f.points} onChange={(e) => setF({ ...f, points: e.target.value })} className="input" placeholder="e.g. 10 or -5" />
            </div>
            <div>
              <label className="label">Reason / note</label>
              <textarea value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} className="input" rows={2} />
            </div>
            <button onClick={submit} disabled={!f.student_id || !f.points || add.isPending} className="btn-primary w-full gap-2">
              {add.isPending ? <Loader2 size={15} className="animate-spin" /> : <PlusCircle size={15} />} Record Point
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-slate-200 p-8 text-sm text-slate-500">You don&apos;t have permission to record points.</div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100 flex items-center gap-2"><Award size={16} className="text-slate-400" /><h2 className="text-sm font-bold text-slate-800">Recent Entries</h2></div>
          {(recent as any[]).length === 0 ? (
            <p className="text-sm text-slate-400 py-10 text-center">No points recorded yet.</p>
          ) : (
            <ul className="divide-y divide-slate-50 max-h-[520px] overflow-y-auto">
              {(recent as any[]).slice(0, 40).map((e) => (
                <li key={e.id} className="px-5 py-3 flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-800 truncate">{e.student_name}</p>
                    <p className="text-xs text-slate-400 truncate">{[e.title, e.term, e.reason].filter(Boolean).join(" · ") || "—"}</p>
                  </div>
                  <span className={cn("text-sm font-bold tabular-nums shrink-0", e.points >= 0 ? "text-emerald-600" : "text-red-600")}>{e.points >= 0 ? `+${e.points}` : e.points}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
