"use client";

import { useMemo, useState } from "react";
import {
  usePromotions, usePreviewPromotions, useCreatePromotions, useRevertPromotion,
  useClassOptions, useClassStudents,
} from "@/hooks/useEnrollment";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import {
  Loader2, AlertTriangle, ArrowRight, GraduationCap, RotateCcw, X, CheckCircle2, Ban,
} from "lucide-react";
import type { PromotionPreview } from "@/types";

const OUTCOMES = ["promoted", "repeated", "graduated"];
const OUTCOME_STYLE: Record<string, string> = {
  promoted: "bg-emerald-50 text-emerald-700 border-emerald-200",
  repeated: "bg-amber-50 text-amber-700 border-amber-200",
  graduated: "bg-indigo-50 text-indigo-700 border-indigo-200",
};

export default function PromotionPage() {
  const canWrite = useHasPermission("school:students:write");
  const { data: classData } = useClassOptions();
  const classes = (classData?.items ?? []) as Array<{ id: string; name: string }>;

  const [fromClass, setFromClass] = useState("");
  const [toClass, setToClass] = useState("");
  const [outcome, setOutcome] = useState("promoted");
  const [academicYear, setAcademicYear] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<PromotionPreview | null>(null);

  const { data: studentData, isLoading: loadingStudents } = useClassStudents(fromClass || null);
  const students = (studentData?.items ?? []) as Array<{ id: string; first_name: string; last_name: string; student_id: string }>;

  const { data: history, isLoading, isError, refetch } = usePromotions();
  const previewMut = usePreviewPromotions();
  const promote = useCreatePromotions();
  const revert = useRevertPromotion();

  const toggle = (id: string) => setSelected((prev) => {
    const next = new Set(prev);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const allSelected = students.length > 0 && students.every((s) => selected.has(s.id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(students.map((s) => s.id)));

  const payload = useMemo(() => ({
    student_ids: Array.from(selected),
    to_class_id: outcome === "graduated" ? undefined : (toClass || undefined),
    from_class_id: fromClass || undefined,
    academic_year: academicYear || undefined,
    outcome,
  }), [selected, outcome, toClass, fromClass, academicYear]);

  const canSubmit = selected.size > 0 && (outcome !== "promoted" || !!toClass) && !previewMut.isPending;

  const runPreview = () => previewMut.mutate(payload, { onSuccess: (p: PromotionPreview) => setPreview(p) });

  const confirmRun = () => {
    const eligibleIds = (preview?.items ?? []).filter((i) => i.eligible).map((i) => i.student_id);
    if (eligibleIds.length === 0) return;
    promote.mutate(
      { ...payload, student_ids: eligibleIds },
      { onSuccess: () => { setPreview(null); setSelected(new Set()); } },
    );
  };

  const rows = history?.items;
  // Most recent un-reverted run → target for "Undo last run".
  const latestBatch = useMemo(() => rows?.find((r) => !r.reverted_at)?.batch_id ?? null, [rows]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Students</span><span>/</span><span className="text-brand-600 font-semibold">Promotion Manager</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Promotion Manager</h1>
        <p className="text-slate-500 text-sm mt-0.5">Move students between classes at term / year roll-over. Preview before you commit; undo a run if needed.</p>
      </div>

      {canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="label">From Class</label>
              <select value={fromClass} onChange={(e) => { setFromClass(e.target.value); setSelected(new Set()); }} className="input">
                <option value="">Select class…</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Outcome</label>
              <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className="input capitalize">
                {OUTCOMES.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
            <div>
              <label className="label">To Class {outcome === "promoted" && "*"}</label>
              <select value={toClass} onChange={(e) => setToClass(e.target.value)} disabled={outcome === "graduated"} className="input">
                <option value="">{outcome === "graduated" ? "— (graduating)" : "Select class…"}</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Academic Year</label>
              <input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} className="input" placeholder="e.g. 2025/2026" />
            </div>
          </div>

          {fromClass && (
            <div className="border border-slate-200 rounded-lg overflow-hidden mb-4">
              <div className="flex items-center justify-between px-4 py-2 bg-slate-50 border-b border-slate-100">
                <span className="text-xs font-semibold text-slate-600">{students.length} student(s)</span>
                {students.length > 0 && (
                  <button onClick={toggleAll} className="text-xs font-semibold text-brand-600 hover:text-brand-700">
                    {allSelected ? "Clear all" : "Select all"}
                  </button>
                )}
              </div>
              <div className="max-h-64 overflow-y-auto divide-y divide-slate-50">
                {loadingStudents ? (
                  <p className="px-4 py-6 text-xs text-slate-400">Loading students…</p>
                ) : students.length === 0 ? (
                  <p className="px-4 py-6 text-xs text-slate-400">No students in this class.</p>
                ) : (
                  students.map((s) => (
                    <label key={s.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 cursor-pointer">
                      <input type="checkbox" checked={selected.has(s.id)} onChange={() => toggle(s.id)} />
                      <span className="text-sm text-slate-700">{s.first_name} {s.last_name}</span>
                      <span className="text-xs text-slate-400 ml-auto font-mono">{s.student_id}</span>
                    </label>
                  ))
                )}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">{selected.size} selected</p>
            <button onClick={runPreview} disabled={!canSubmit} className="btn-primary gap-2">
              {previewMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
              Preview {outcome}
            </button>
          </div>
        </div>
      )}

      {/* History */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-bold text-slate-800">Promotion History</h2>
        {canWrite && latestBatch && (
          <button
            onClick={() => { if (confirm("Undo the most recent promotion run? Students will be restored to their previous class/status.")) revert.mutate(latestBatch); }}
            disabled={revert.isPending}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-600 hover:text-amber-700 border border-amber-200 bg-amber-50 px-3 py-1.5 rounded-lg"
          >
            {revert.isPending ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
            Undo last run
          </button>
        )}
      </div>
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Student", "From", "To", "Outcome", "Year", "Date"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center">
                <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                <p className="text-sm font-semibold text-slate-600">Couldn’t load history.</p>
                <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
              </td></tr>
            ) : rows && rows.length > 0 ? (
              rows.map((p) => (
                <tr key={p.id} className={cn("hover:bg-slate-50/70", p.reverted_at && "opacity-50")}>
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">
                    {p.student_name || p.student_id.slice(0, 8)}
                    {p.reverted_at && <span className="ml-2 text-[10px] font-bold uppercase text-amber-600">reverted</span>}
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600">{p.from_class_name || "—"}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{p.to_class_name || (p.outcome === "graduated" ? "Graduated" : "—")}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", OUTCOME_STYLE[p.outcome] || "")}>{p.outcome}</span></td>
                  <td className="px-5 py-4 text-xs text-slate-500">{p.academic_year || "—"}</td>
                  <td className="px-5 py-4 text-xs text-slate-500">{formatDate(p.created_at)}</td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400">
                <GraduationCap size={36} className="mx-auto mb-3 opacity-40" />
                <p className="font-semibold">No promotions recorded yet</p>
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Preview / confirm modal */}
      {preview && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setPreview(null)}>
          <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-800">Confirm promotion</h3>
              <button onClick={() => setPreview(null)} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
            </div>
            <div className="px-6 py-4 overflow-y-auto">
              <p className="text-sm text-slate-600 mb-3">
                <span className="font-semibold capitalize">{preview.outcome}</span>
                {preview.to_class_name ? <> → <span className="font-semibold">{preview.to_class_name}</span></> : null}
              </p>
              <div className="flex gap-4 mb-4 text-sm">
                <span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 size={15} /> {preview.eligible_count} eligible</span>
                {preview.skipped_count > 0 && <span className="inline-flex items-center gap-1 text-rose-600"><Ban size={15} /> {preview.skipped_count} skipped</span>}
              </div>
              <ul className="border border-slate-100 rounded-lg divide-y divide-slate-50 max-h-64 overflow-y-auto">
                {preview.items.map((i) => (
                  <li key={i.student_id} className="flex items-center justify-between px-3 py-2 text-sm">
                    <span className={cn(i.eligible ? "text-slate-700" : "text-slate-400 line-through")}>{i.student_name || i.student_id.slice(0, 8)}</span>
                    {i.eligible
                      ? <span className="text-xs text-slate-400">{i.from_class_name || "—"}</span>
                      : <span className="text-[11px] text-rose-500">{i.reason}</span>}
                  </li>
                ))}
              </ul>
              {preview.skipped_count > 0 && (
                <p className="text-xs text-slate-400 mt-2">Skipped students won’t be changed; only the {preview.eligible_count} eligible will be processed.</p>
              )}
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100">
              <button onClick={() => setPreview(null)} className="btn-secondary">Cancel</button>
              <button onClick={confirmRun} disabled={preview.eligible_count === 0 || promote.isPending} className="btn-primary gap-2">
                {promote.isPending && <Loader2 size={15} className="animate-spin" />}
                Confirm {preview.eligible_count} student(s)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
