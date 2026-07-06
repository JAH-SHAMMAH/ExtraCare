"use client";

import { useMemo, useState } from "react";
import {
  useFeeRecords, useCreateFeeRecord, useUpdateFeeRecord, useDeleteFeeRecord, useAssignClassFees, useFinanceClasses,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn } from "@/lib/utils";
import { Wallet, Plus, X, Loader2, Trash2, Pencil, AlertTriangle, User, Users } from "lucide-react";
import type { FeeRecord, ClassOption } from "@/types";

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const TERMS = [{ v: "term1", l: "Term 1" }, { v: "term2", l: "Term 2" }, { v: "term3", l: "Term 3" }, { v: "annual", l: "Annual" }];
const FEES: { key: keyof Breakdown; label: string }[] = [
  { key: "tuition_fee", label: "Tuition" }, { key: "exam_fee", label: "Exam" }, { key: "activity_fee", label: "Activity" },
  { key: "transport_fee", label: "Transport" }, { key: "hostel_fee", label: "Hostel" }, { key: "other_fees", label: "Other" },
];
type Breakdown = { tuition_fee: string; exam_fee: string; activity_fee: string; transport_fee: string; hostel_fee: string; other_fees: string };

const STATUS_STYLE: Record<string, string> = {
  paid: "bg-emerald-50 text-emerald-700 border-emerald-200",
  partial: "bg-amber-50 text-amber-700 border-amber-200",
  unpaid: "bg-slate-100 text-slate-600 border-slate-200",
};

const emptyBreakdown = (): Breakdown => ({ tuition_fee: "", exam_fee: "", activity_fee: "", transport_fee: "", hostel_fee: "", other_fees: "" });

export default function FeeAssignmentPage() {
  const canWrite = useHasPermission("payments:write");
  const { data: records, isLoading, isError, refetch } = useFeeRecords();
  const { data: classesData } = useFinanceClasses();
  const classes: ClassOption[] = classesData ?? [];

  const create = useCreateFeeRecord();
  const update = useUpdateFeeRecord();
  const del = useDeleteFeeRecord();
  const assignClass = useAssignClassFees();

  const [show, setShow] = useState(false);
  const [mode, setMode] = useState<"student" | "class">("student");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [target, setTarget] = useState({ student_id: "", student_name: "", class_id: "" });
  const [meta, setMeta] = useState({ term: "term1", session_year: String(new Date().getFullYear()), due_date: "" });
  const [breakdown, setBreakdown] = useState<Breakdown>(emptyBreakdown());

  const total = useMemo(() => FEES.reduce((s, f) => s + (Number(breakdown[f.key]) || 0), 0), [breakdown]);

  const reset = () => {
    setShow(false); setEditingId(null); setMode("student");
    setTarget({ student_id: "", student_name: "", class_id: "" });
    setMeta({ term: "term1", session_year: String(new Date().getFullYear()), due_date: "" });
    setBreakdown(emptyBreakdown());
  };

  const openEdit = (r: FeeRecord) => {
    setMode("student"); setEditingId(r.id);
    setTarget({ student_id: r.student_id, student_name: r.student_name ?? "", class_id: "" });
    setMeta({ term: r.term, session_year: r.session_year, due_date: r.due_date ?? "" });
    setBreakdown({
      tuition_fee: String(r.tuition_fee || ""), exam_fee: String(r.exam_fee || ""), activity_fee: String(r.activity_fee || ""),
      transport_fee: String(r.transport_fee || ""), hostel_fee: String(r.hostel_fee || ""), other_fees: String(r.other_fees || ""),
    });
    setShow(true);
  };

  const targetOk = mode === "student" ? !!target.student_id : !!target.class_id;
  const canSubmit = total > 0 && targetOk && meta.term && meta.session_year;

  const breakdownPayload = () => Object.fromEntries(FEES.map((f) => [f.key, Number(breakdown[f.key]) || 0]));

  const submit = () => {
    if (!canSubmit) return;
    const base = { ...breakdownPayload(), due_date: meta.due_date || null };
    if (mode === "class") {
      assignClass.mutate({ class_id: target.class_id, term: meta.term, session_year: meta.session_year, ...base }, { onSuccess: reset });
    } else if (editingId) {
      update.mutate({ id: editingId, data: base }, { onSuccess: reset });
    } else {
      create.mutate({ student_id: target.student_id, term: meta.term, session_year: meta.session_year, ...base }, { onSuccess: reset });
    }
  };

  const pending = create.isPending || update.isPending || assignClass.isPending;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Fee Assignment</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Fee Assignment</h1>
          <p className="text-slate-500 text-sm mt-0.5">Set what students owe for a term. This is the source of the balances parents see, and what discounts apply against.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Assign Fees</button>}
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">{editingId ? "Edit fee record" : "Assign fees"}</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>

          {!editingId && (
            <div className="flex gap-2 mb-4">
              <button type="button" onClick={() => setMode("student")} className={cn("flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold", mode === "student" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><User size={15} /> One student</button>
              <button type="button" onClick={() => setMode("class")} className={cn("flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-semibold", mode === "class" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><Users size={15} /> Whole class</button>
            </div>
          )}

          {/* Target + meta — student picker must be in a plain grid (never an
              overflow-hidden / table wrapper, which clips its dropdown). */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <div className="md:col-span-3">
              {mode === "student" ? (
                <>
                  <label className="label">Student *</label>
                  {editingId ? (
                    <div className="input bg-slate-50 text-slate-600">{target.student_name || target.student_id}</div>
                  ) : (
                    <EntityPicker type="student" value={target.student_id || null} valueLabel={target.student_name || null}
                      onChange={(id, label) => setTarget({ ...target, student_id: id || "", student_name: label || "" })}
                      placeholder="Search students by name or ID…" />
                  )}
                </>
              ) : (
                <>
                  <label className="label">Class *</label>
                  <select value={target.class_id} onChange={(e) => setTarget({ ...target, class_id: e.target.value })} className="input">
                    <option value="">Select class…</option>
                    {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.student_count != null ? ` (${c.student_count})` : ""}</option>)}
                  </select>
                  <p className="text-[11px] text-slate-400 mt-1">Creates a fee record for every student in the class; anyone already assigned this term is skipped.</p>
                </>
              )}
            </div>
            <div>
              <label className="label">Term *</label>
              <select value={meta.term} onChange={(e) => setMeta({ ...meta, term: e.target.value })} disabled={!!editingId} className="input disabled:bg-slate-50">
                {TERMS.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}
              </select>
            </div>
            <div><label className="label">Session year *</label><input value={meta.session_year} onChange={(e) => setMeta({ ...meta, session_year: e.target.value })} disabled={!!editingId} className="input disabled:bg-slate-50" placeholder="2026" /></div>
            <div><label className="label">Due date</label><input type="date" value={meta.due_date} onChange={(e) => setMeta({ ...meta, due_date: e.target.value })} className="input" /></div>
          </div>

          <label className="label">Fee breakdown *</label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-3">
            {FEES.map((f) => (
              <div key={f.key}>
                <label className="text-[11px] text-slate-500">{f.label} (₦)</label>
                <input type="number" min="0" value={breakdown[f.key]} onChange={(e) => setBreakdown({ ...breakdown, [f.key]: e.target.value })} className="input" placeholder="0" />
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mb-4"><span className="text-xs text-slate-400">Set at least one component.</span><div className="text-sm text-slate-600">Total: <span className="font-bold text-slate-900">{naira(total)}</span></div></div>

          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || pending} className="btn-primary gap-2">{pending && <Loader2 size={15} className="animate-spin" />}{editingId ? "Save changes" : mode === "class" ? "Assign to class" : "Assign fees"}</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Term", "Total", "Paid", "Discount", "Outstanding", "Status", ""].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 8 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-16" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={8} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load fee records.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : records && records.length > 0 ? (
              records.map((r: FeeRecord) => (
                <tr key={r.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{r.student_name || r.student_id.slice(0, 8)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 capitalize">{r.term} · {r.session_year}</td>
                  <td className="px-5 py-4 text-sm text-slate-700">{naira(r.total_fee)}</td>
                  <td className="px-5 py-4 text-sm text-slate-500">{naira(r.paid_amount)}</td>
                  <td className="px-5 py-4 text-sm text-slate-500">{r.discount_amount ? naira(r.discount_amount) : "—"}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{naira(r.outstanding_balance)}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[r.payment_status] || "")}>{r.payment_status}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => openEdit(r)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Pencil size={14} /></button>
                        <button onClick={() => { if (confirm("Delete this fee record?")) del.mutate(r.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={8} className="py-16 text-center text-slate-400"><Wallet size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No fees assigned yet</p>{canWrite && <button onClick={() => { reset(); setShow(true); }} className="text-brand-600 hover:text-brand-700 text-sm font-semibold mt-1">Assign fees to a class or student →</button>}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
