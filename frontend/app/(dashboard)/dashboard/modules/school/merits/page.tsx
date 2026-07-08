"use client";

import { useState } from "react";
import {
  useRecognitions, useLeaderboard, useCreateRecognition, useDeleteRecognition,
} from "@/hooks/useAcademics";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import {
  Award, Plus, X, Loader2, Trash2, AlertTriangle, Trophy, Medal, TrendingUp, TrendingDown,
} from "lucide-react";

const AWARD_TYPES = ["honor_roll", "prize", "certificate"];

type Tab = "conduct" | "awards";

export default function MeritsPage() {
  const canWrite = useHasPermission("school:behaviour:write");
  const [tab, setTab] = useState<Tab>("conduct");

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Pastoral &amp; Welfare</span><span>/</span><span className="text-brand-600 font-semibold">Merit &amp; Awards</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Merit &amp; Awards</h1>
        <p className="text-slate-500 text-sm mt-0.5">House conduct points and academic recognition — one record, two views.</p>
      </div>

      <div className="flex gap-1 border-b border-slate-200 mb-6">
        {([["conduct", "Conduct Points"], ["awards", "Academic Awards"]] as [Tab, string][]).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={cn(
            "px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition",
            tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-700",
          )}>{label}</button>
        ))}
      </div>

      {tab === "conduct" ? <ConductTab canWrite={canWrite} /> : <AwardsTab canWrite={canWrite} />}
    </div>
  );
}

function ConductTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useRecognitions({ type: "conduct_point" });
  const { data: board } = useLeaderboard();
  const create = useCreateRecognition();
  const remove = useDeleteRecognition();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ student_id: "", points: "", house: "", category: "", reason: "", term: "" });

  const reset = () => { setForm({ student_id: "", points: "", house: "", category: "", reason: "", term: "" }); setShow(false); };
  const submit = () => create.mutate(
    { type: "conduct_point", student_id: form.student_id, points: form.points ? Number(form.points) : 0, house: form.house || null, category: form.category || null, reason: form.reason || null, term: form.term || null },
    { onSuccess: reset },
  );

  const houses = board?.houses ?? [];
  const rows = data?.items;

  return (
    <>
      {/* House leaderboard */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {houses.length === 0 ? (
          <div className="col-span-full bg-white rounded-xl border border-slate-200 p-5 text-sm text-slate-400 flex items-center gap-2"><Trophy size={16} /> No house points yet.</div>
        ) : houses.map((h, i) => (
          <div key={h.house} className={cn("bg-white rounded-xl border p-4", i === 0 ? "border-amber-300 ring-1 ring-amber-200" : "border-slate-200")}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-bold text-slate-800">{h.house}</span>
              {i === 0 ? <Trophy size={16} className="text-amber-500" /> : <Medal size={16} className="text-slate-300" />}
            </div>
            <p className="text-2xl font-black text-slate-900">{h.total_points}</p>
            <p className="text-[11px] text-slate-400">{h.entries} entries</p>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-bold text-slate-800">Conduct Points</h2>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Award / Deduct</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h3 className="text-sm font-bold text-slate-800">Conduct Point</h3><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2"><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Points * (use − to deduct)</label><input type="number" value={form.points} onChange={(e) => setForm({ ...form, points: e.target.value })} className="input" placeholder="e.g. 5 or -2" /></div>
            <div><label className="label">House</label><input value={form.house} onChange={(e) => setForm({ ...form, house: e.target.value })} className="input" placeholder="e.g. Red" /></div>
            <div><label className="label">Category</label><input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input" placeholder="helpfulness / lateness" /></div>
            <div><label className="label">Term</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input" placeholder="Term 1" /></div>
            <div className="md:col-span-3"><label className="label">Reason</label><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.student_id || !form.points || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Record</button>
          </div>
        </div>
      )}

      <RecognitionTable rows={rows} isLoading={isLoading} isError={isError} refetch={refetch} canWrite={canWrite} onDelete={(id) => remove.mutate(id)} kind="conduct" />
    </>
  );
}

function AwardsTab({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading, isError, refetch } = useRecognitions({ type: "academic_award" });
  const create = useCreateRecognition();
  const remove = useDeleteRecognition();
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ student_id: "", title: "", award_type: "honor_roll", term: "", reason: "" });

  const reset = () => { setForm({ student_id: "", title: "", award_type: "honor_roll", term: "", reason: "" }); setShow(false); };
  const submit = () => create.mutate(
    { type: "academic_award", student_id: form.student_id, title: form.title || null, award_type: form.award_type, term: form.term || null, reason: form.reason || null },
    { onSuccess: reset },
  );

  const rows = data?.items;

  return (
    <>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-bold text-slate-800">Academic Awards</h2>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Award</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h3 className="text-sm font-bold text-slate-800">Academic Award</h3><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div><label className="label">Student *</label><EntityPicker type="student" value={form.student_id || null} onChange={(id) => setForm({ ...form, student_id: id || "" })} /></div>
            <div><label className="label">Title</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="input" placeholder="e.g. Top in Mathematics" /></div>
            <div><label className="label">Award Type</label>
              <select value={form.award_type} onChange={(e) => setForm({ ...form, award_type: e.target.value })} className="input capitalize">
                {AWARD_TYPES.map((a) => <option key={a} value={a}>{a.replace("_", " ")}</option>)}
              </select>
            </div>
            <div><label className="label">Term</label><input value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} className="input" placeholder="Term 1" /></div>
            <div className="md:col-span-2"><label className="label">Description</label><input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button onClick={submit} disabled={!form.student_id || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Save</button>
          </div>
        </div>
      )}

      <RecognitionTable rows={rows} isLoading={isLoading} isError={isError} refetch={refetch} canWrite={canWrite} onDelete={(id) => remove.mutate(id)} kind="award" />
    </>
  );
}

function RecognitionTable({ rows, isLoading, isError, refetch, canWrite, onDelete, kind }: {
  rows: any[] | undefined; isLoading: boolean; isError: boolean; refetch: () => void;
  canWrite: boolean; onDelete: (id: string) => void; kind: "conduct" | "award";
}) {
  const headers = kind === "conduct"
    ? ["Student", "Points", "House", "Category", "Date", ""]
    : ["Student", "Award", "Type", "Term", "Date", ""];

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <table className="w-full text-left">
        <thead><tr className="bg-slate-50/80 border-b border-slate-100">{headers.map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-slate-50">
          {isLoading ? (
            Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
          ) : isError ? (
            <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load records.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
          ) : rows && rows.length > 0 ? (
            rows.map((r) => (
              <tr key={r.id} className="hover:bg-slate-50/70">
                <td className="px-5 py-4 text-sm font-medium text-slate-800">{r.student_name || r.student_id.slice(0, 8)}</td>
                {kind === "conduct" ? (
                  <>
                    <td className="px-5 py-4">
                      <span className={cn("inline-flex items-center gap-1 text-sm font-semibold", (r.points ?? 0) >= 0 ? "text-emerald-600" : "text-rose-600")}>
                        {(r.points ?? 0) >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}{r.points}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">{r.house || "—"}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{r.category || "—"}</td>
                  </>
                ) : (
                  <>
                    <td className="px-5 py-4 text-sm text-slate-700">{r.title || "—"}</td>
                    <td className="px-5 py-4 text-sm text-slate-600 capitalize">{(r.award_type || "—").replace("_", " ")}</td>
                    <td className="px-5 py-4 text-sm text-slate-600">{r.term || "—"}</td>
                  </>
                )}
                <td className="px-5 py-4 text-xs text-slate-500">{formatDate(r.created_at)}</td>
                <td className="px-5 py-4">{canWrite && <button onClick={() => { if (confirm("Remove this record?")) onDelete(r.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}</td>
              </tr>
            ))
          ) : (
            <tr><td colSpan={6} className="py-16 text-center text-slate-400"><Award size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No records yet</p></td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
