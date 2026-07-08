"use client";

import { useState } from "react";
import {
  useDiscounts, useCreateDiscount, useApproveDiscount, useRejectDiscount,
  useVoidDiscount, useDeleteDiscount,
} from "@/hooks/useFinance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import {
  BadgePercent, Plus, X, Loader2, Trash2, AlertTriangle, CheckCircle2, Ban, XCircle, ShieldCheck,
} from "lucide-react";
import type { FeeDiscount } from "@/types";

const STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600 border-slate-200",
  approved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected: "bg-amber-50 text-amber-700 border-amber-200",
  void: "bg-rose-50 text-rose-700 border-rose-200",
};

const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const REASONS = ["Scholarship", "Sibling discount", "Staff child", "Hardship waiver", "Early payment", "Other"];

export default function DiscountsPage() {
  const canWrite = useHasPermission("payments:write");
  const canPost = useHasPermission("payments:post");
  const [statusFilter, setStatusFilter] = useState("");
  const [show, setShow] = useState(false);

  const { data: discounts, isLoading, isError, refetch } = useDiscounts(statusFilter ? { status: statusFilter } : undefined);
  const create = useCreateDiscount();
  const approve = useApproveDiscount();
  const reject = useRejectDiscount();
  const voidDiscount = useVoidDiscount();
  const del = useDeleteDiscount();

  const [form, setForm] = useState<{ student_id: string; student_name: string; discount_type: "fixed" | "percent"; value: string; reason: string }>(
    { student_id: "", student_name: "", discount_type: "fixed", value: "", reason: "Scholarship" },
  );
  const reset = () => { setForm({ student_id: "", student_name: "", discount_type: "fixed", value: "", reason: "Scholarship" }); setShow(false); };

  const canSubmit = form.student_id && Number(form.value) > 0;
  const submit = () => {
    if (!canSubmit) return;
    create.mutate(
      { student_id: form.student_id, discount_type: form.discount_type, value: Number(form.value), reason: form.reason || null },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Finance</span><span>/</span><span className="text-brand-600 font-semibold">Manage Discounts</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Discounts</h1>
          <p className="text-slate-500 text-sm mt-0.5">Grant scholarships, sibling discounts and waivers. Approval reduces the student's fee balance and posts a ledger contra.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Discount</button>}
      </div>

      <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-5">
        <ShieldCheck size={14} className="mt-0.5 shrink-0" />
        <span>Two-person control: a discount can't be approved by the person who proposed it. Approval reduces the student's outstanding fees (shown to parents) <b>and</b> posts <span className="font-mono">Dr Fee Discounts / Cr Receivable</span>. Approved discounts are voided (reversed), never deleted.</span>
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {["draft", "approved", "rejected", "void"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Propose a discount</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          {/* Grid layout — the student picker must NOT sit in an overflow-hidden / table
              wrapper (that clips its dropdown). Plain grid cells only. */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="md:col-span-2">
              <label className="label">Student *</label>
              <EntityPicker type="student" value={form.student_id || null} valueLabel={form.student_name || null}
                onChange={(id, label) => setForm({ ...form, student_id: id || "", student_name: label || "" })}
                placeholder="Search students by name or ID…" />
            </div>
            <div>
              <label className="label">Type *</label>
              <div className="flex gap-2">
                <button type="button" onClick={() => setForm({ ...form, discount_type: "fixed" })} className={cn("flex-1 rounded-lg border px-3 py-2 text-sm font-semibold", form.discount_type === "fixed" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}>Fixed (₦)</button>
                <button type="button" onClick={() => setForm({ ...form, discount_type: "percent" })} className={cn("flex-1 rounded-lg border px-3 py-2 text-sm font-semibold", form.discount_type === "percent" ? "border-brand-300 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}>Percent (%)</button>
              </div>
            </div>
            <div>
              <label className="label">{form.discount_type === "percent" ? "Percent of total fee *" : "Amount (₦) *"}</label>
              <input type="number" min="0" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} className="input" placeholder={form.discount_type === "percent" ? "e.g. 20" : "e.g. 50000"} />
            </div>
            <div className="md:col-span-2">
              <label className="label">Reason</label>
              <select value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} className="input">
                {REASONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mb-4">Applies to the student's most recent fee record. A percent is taken off the total fee; the discount can't exceed what's still owed.</p>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Propose discount</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Type", "Amount", "Reason", "Status", "Actions"].map((h) => <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 4 }).map((_, i) => <tr key={i}>{Array.from({ length: 6 }).map((_, j) => <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>)}</tr>)
            ) : isError ? (
              <tr><td colSpan={6} className="py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load discounts.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></td></tr>
            ) : discounts && discounts.length > 0 ? (
              discounts.map((d: FeeDiscount) => (
                <tr key={d.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4 text-sm font-medium text-slate-800">{d.student_name || d.student_id.slice(0, 8)}<span className="block text-[11px] text-slate-400">{formatDate(d.created_at)}</span></td>
                  <td className="px-5 py-4 text-sm text-slate-600 capitalize">{d.discount_type === "percent" ? `${d.value}%` : "Fixed"}</td>
                  <td className="px-5 py-4 text-sm font-semibold text-slate-800">{naira(d.amount)}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{d.reason || "—"}</td>
                  <td className="px-5 py-4"><span className={cn("badge capitalize", STATUS_STYLE[d.status] || "")}>{d.status}</span></td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1">
                      {d.status === "draft" && canPost && <button onClick={() => { if (confirm(`Approve ${naira(d.amount)} discount for ${d.student_name}? This reduces their fees and posts to the ledger.`)) approve.mutate(d.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700 px-2 py-1 rounded hover:bg-emerald-50"><CheckCircle2 size={13} /> Approve</button>}
                      {d.status === "draft" && canPost && <button onClick={() => { if (confirm("Reject this discount?")) reject.mutate(d.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-amber-600 hover:text-amber-700 px-2 py-1 rounded hover:bg-amber-50"><XCircle size={13} /> Reject</button>}
                      {d.status === "approved" && canPost && <button onClick={() => { if (confirm(`Void this discount? This restores ${d.student_name}'s balance and reverses the ledger entry.`)) voidDiscount.mutate(d.id); }} className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 hover:text-rose-700 px-2 py-1 rounded hover:bg-rose-50"><Ban size={13} /> Void</button>}
                      {(d.status === "draft" || d.status === "rejected") && canWrite && <button onClick={() => { if (confirm("Delete this discount?")) del.mutate(d.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))
            ) : (
              <tr><td colSpan={6} className="py-16 text-center text-slate-400"><BadgePercent size={36} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">No discounts yet</p></td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
