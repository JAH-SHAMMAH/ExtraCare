"use client";

import { useMemo, useState } from "react";
import {
  useHostels, useHostelStudents, useHostelLifeGrades, useHostelCommentBank,
  useHostelLifeComments, useAddHostelLifeComment, useDeleteHostelLifeComment, useHostelResults,
} from "@/hooks/usePastoral";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Loader2, Heart, Trash2, ClipboardList } from "lucide-react";

const TERMS = ["Autumn Term", "Spring Term", "Summer Term"];
type Tab = "entry" | "results";

export default function HostelLifePage() {
  const canWrite = useHasPermission("school:hostel:write");
  const [tab, setTab] = useState<Tab>("entry");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral</span><span>/</span><span className="text-brand-600 font-semibold">Hostel Life</span></nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-1 flex items-center gap-2"><Heart size={22} className="text-brand-600" /> Hostel Life</h1>
      <p className="text-slate-500 text-sm mb-5">Per-boarder life comments and grades, and the aggregated result view.</p>

      <div className="inline-flex gap-1 bg-slate-100 rounded-lg p-1 mb-6">
        {([["entry", "Life Comments"], ["results", "Result View"]] as [Tab, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={cn("px-3.5 py-1.5 text-sm font-semibold rounded-md transition", tab === k ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-700")}>{l}</button>
        ))}
      </div>

      {tab === "entry" ? <LifeComments canWrite={canWrite} /> : <ResultView />}
    </div>
  );
}

function LifeComments({ canWrite }: { canWrite: boolean }) {
  const { data: hostelData } = useHostels();
  const hostels = hostelData?.items ?? [];
  const [f, setF] = useState({ hostel_id: "", student_id: "", term: "Autumn Term", grade: "", comment: "" });
  const { data: roster = [] } = useHostelStudents(f.hostel_id ? { hostel_id: f.hostel_id } : undefined);
  const { data: grades = [] } = useHostelLifeGrades();
  const { data: bank = [] } = useHostelCommentBank();
  const { data: comments = [] } = useHostelLifeComments(f.student_id ? { student_id: f.student_id } : undefined);
  const add = useAddHostelLifeComment();
  const del = useDeleteHostelLifeComment();

  const activeGrades = useMemo(() => (grades as any[]).filter((g) => g.is_active), [grades]);
  const activeBank = useMemo(() => (bank as any[]).filter((c) => c.is_active), [bank]);

  const submit = () => {
    if (!f.student_id) return;
    add.mutate(
      { student_id: f.student_id, hostel_id: f.hostel_id || null, term: f.term, grade: f.grade || null, comment: f.comment || null },
      { onSuccess: () => setF((p) => ({ ...p, comment: "", grade: "" })) },
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {canWrite ? (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Hostel</label>
              <select value={f.hostel_id} onChange={(e) => setF({ ...f, hostel_id: e.target.value, student_id: "" })} className="input">
                <option value="">All hostels</option>
                {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
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
            <label className="label">Boarder</label>
            <select value={f.student_id} onChange={(e) => setF({ ...f, student_id: e.target.value })} className="input">
              <option value="">— Select —</option>
              {(roster as any[]).map((r) => <option key={r.student_id} value={r.student_id}>{r.student_name}{r.hostel_name ? ` · ${r.hostel_name}` : ""}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Grade</label>
            <select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })} className="input">
              <option value="">— None —</option>
              {activeGrades.map((g) => <option key={g.id} value={g.name}>{g.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Comment</label>
            <textarea value={f.comment} onChange={(e) => setF({ ...f, comment: e.target.value })} className="input" rows={3} />
            {activeBank.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {activeBank.slice(0, 12).map((c) => (
                  <button key={c.id} type="button" onClick={() => setF((p) => ({ ...p, comment: p.comment ? `${p.comment} ${c.text}` : c.text }))} className="text-[11px] px-2 py-1 rounded-full bg-slate-100 text-slate-600 hover:bg-brand-50 hover:text-brand-700">+ {c.text.length > 32 ? c.text.slice(0, 32) + "…" : c.text}</button>
                ))}
              </div>
            )}
          </div>
          <button onClick={submit} disabled={!f.student_id || add.isPending} className="btn-primary w-full gap-2">{add.isPending ? <Loader2 size={15} className="animate-spin" /> : <Heart size={15} />} Record Comment</button>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-sm text-slate-500">You don&apos;t have permission to record hostel life comments.</div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100"><h2 className="text-sm font-bold text-slate-800">{f.student_id ? "This boarder's comments" : "Select a boarder"}</h2></div>
        {!f.student_id ? (
          <p className="text-sm text-slate-400 py-10 text-center">Pick a boarder to see their history.</p>
        ) : (comments as any[]).length === 0 ? (
          <p className="text-sm text-slate-400 py-10 text-center">No comments yet.</p>
        ) : (
          <ul className="divide-y divide-slate-50 max-h-[520px] overflow-y-auto">
            {(comments as any[]).map((c) => (
              <li key={c.id} className="px-5 py-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {c.grade && <span className="badge bg-brand-50 text-brand-700 border-brand-200">{c.grade}</span>}
                    <span className="text-xs text-slate-400">{[c.term, c.recorded_on].filter(Boolean).join(" · ")}</span>
                  </div>
                  {c.comment && <p className="text-sm text-slate-700 mt-1">{c.comment}</p>}
                </div>
                {canWrite && <button onClick={() => del.mutate(c.id)} className="text-slate-400 hover:text-red-600 p-1 shrink-0"><Trash2 size={14} /></button>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ResultView() {
  const { data: hostelData } = useHostels();
  const hostels = hostelData?.items ?? [];
  const [hostelId, setHostelId] = useState("");
  const [term, setTerm] = useState("");
  const { data: rows = [], isLoading } = useHostelResults({ hostel_id: hostelId || undefined, term: term || undefined });

  return (
    <div>
      <div className="flex flex-wrap gap-3 mb-5">
        <select value={hostelId} onChange={(e) => setHostelId(e.target.value)} className="input w-auto">
          <option value="">All hostels</option>
          {(hostels as any[]).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        <select value={term} onChange={(e) => setTerm(e.target.value)} className="input w-auto">
          <option value="">All terms</option>
          {TERMS.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        {isLoading ? (
          <div className="py-16 text-center"><Loader2 className="w-5 h-5 animate-spin mx-auto text-slate-400" /></div>
        ) : rows.length === 0 ? (
          <div className="py-14 text-center text-slate-400"><ClipboardList size={30} className="mx-auto mb-3 opacity-40" /><p className="text-sm">No hostel life records yet.</p></div>
        ) : (
          <table className="w-full text-left">
            <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Boarder", "Hostel", "Latest Grade", "Comments", "Notes"].map((h) => <th key={h} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-slate-50">
              {(rows as any[]).map((r) => (
                <tr key={r.student_id} className="hover:bg-slate-50/70 align-top">
                  <td className="px-4 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">{r.hostel_name || "—"}</td>
                  <td className="px-4 py-3">{r.latest_grade ? <span className="badge bg-brand-50 text-brand-700 border-brand-200">{r.latest_grade}</span> : <span className="text-sm text-slate-400">—</span>}</td>
                  <td className="px-4 py-3 text-sm text-slate-600 tabular-nums">{r.comment_count}</td>
                  <td className="px-4 py-3 text-xs text-slate-500 max-w-md">{(r.comments || []).slice(0, 3).join(" · ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
