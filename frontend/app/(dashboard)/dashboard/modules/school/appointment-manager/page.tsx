"use client";

import { useState } from "react";
import { useAppointments, useCreateAppointment, useUpdateAppointment, useDeleteAppointment } from "@/hooks/useHrExtended";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import { BriefcaseBusiness, Plus, X, Loader2, Trash2, AlertTriangle, Lock } from "lucide-react";

const TYPES = [
  { v: "appointment", l: "Appointment" }, { v: "promotion", l: "Promotion" }, { v: "salary_review", l: "Salary review" },
  { v: "contract_renewal", l: "Contract renewal" }, { v: "transfer", l: "Transfer" }, { v: "termination", l: "Termination" },
];
const typeLabel = (v: string) => TYPES.find((t) => t.v === v)?.l ?? v;
const TYPE_STYLE: Record<string, string> = {
  appointment: "bg-blue-50 text-blue-700 border-blue-200",
  promotion: "bg-emerald-50 text-emerald-700 border-emerald-200",
  salary_review: "bg-violet-50 text-violet-700 border-violet-200",
  contract_renewal: "bg-sky-50 text-sky-700 border-sky-200",
  transfer: "bg-amber-50 text-amber-700 border-amber-200",
  termination: "bg-rose-50 text-rose-700 border-rose-200",
};
const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ended: "bg-slate-100 text-slate-500 border-slate-200",
};
const naira = (n: number) => `₦${(n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const empty = () => ({ staff_user_id: "", staff_name: "", appointment_type: "appointment", title: "", grade: "", salary: "", effective_date: "", end_date: "", reference: "", notes: "" });

export default function AppointmentManagerPage() {
  const canWrite = useHasPermission("hr:write");
  const [statusFilter, setStatusFilter] = useState("");
  const { data, isLoading, isError, refetch } = useAppointments(statusFilter ? { status: statusFilter } : undefined);
  const create = useCreateAppointment();
  const update = useUpdateAppointment();
  const del = useDeleteAppointment();
  const [show, setShow] = useState(false);
  const [f, setF] = useState(empty());
  const reset = () => { setF(empty()); setShow(false); };

  const canSubmit = f.staff_user_id && f.title.trim();
  const submit = () => {
    if (!canSubmit) return;
    create.mutate({
      staff_user_id: f.staff_user_id, appointment_type: f.appointment_type, title: f.title.trim(),
      grade: f.grade.trim() || null, salary: f.salary ? Number(f.salary) : null,
      effective_date: f.effective_date || null, end_date: f.end_date || null,
      reference: f.reference.trim() || null, notes: f.notes.trim() || null,
    }, { onSuccess: reset });
  };

  if (!canWrite) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-10 text-center text-slate-500">
          <Lock size={32} className="mx-auto mb-3 opacity-40" />
          <p className="font-semibold">Appointment records are HR-admin only.</p>
          <p className="text-sm mt-1">They hold staff salary data and require the <span className="font-mono">hr:write</span> permission.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR</span><span>/</span><span className="text-brand-600 font-semibold">Appointment Manager</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Appointment Manager</h1>
          <p className="text-slate-500 text-sm mt-0.5">Staff appointment, promotion and contract history — grade, salary and effective date. Confidential; every change is audit-logged. Each event is a new record (a salary revision is a new "salary review", not an edit).</p>
        </div>
        <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> New Record</button>
      </div>

      <div className="mb-5"><select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize"><option value="">All statuses</option>{["active", "ended"].map((s) => <option key={s} value={s}>{s}</option>)}</select></div>

      {show && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">New appointment record</h2><button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          {/* Grid layout — staff picker never in an overflow-hidden / table wrapper. */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div><label className="label">Staff member *</label><EntityPicker type="staff" value={f.staff_user_id || null} valueLabel={f.staff_name || null} onChange={(id, label) => setF({ ...f, staff_user_id: id || "", staff_name: label || "" })} placeholder="Search staff by name or email…" /></div>
            <div><label className="label">Type *</label><select value={f.appointment_type} onChange={(e) => setF({ ...f, appointment_type: e.target.value })} className="input">{TYPES.map((t) => <option key={t.v} value={t.v}>{t.l}</option>)}</select></div>
            <div><label className="label">Position / title *</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} className="input" placeholder="e.g. Senior Teacher" /></div>
            <div><label className="label">Salary grade</label><input value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })} className="input" placeholder="e.g. TS3 / Grade 8" /></div>
            <div><label className="label">Salary (₦)</label><input type="number" min="0" value={f.salary} onChange={(e) => setF({ ...f, salary: e.target.value })} className="input" placeholder="180000" /></div>
            <div><label className="label">Appointment-letter ref</label><input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} className="input" placeholder="APT/2026/017" /></div>
            <div><label className="label">Effective date</label><input type="date" value={f.effective_date} onChange={(e) => setF({ ...f, effective_date: e.target.value })} className="input" /></div>
            <div><label className="label">End date (contracts)</label><input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} className="input" /></div>
            <div className="md:col-span-2"><label className="label">Notes</label><textarea value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} className="input min-h-[70px]" /></div>
          </div>
          <div className="flex justify-end gap-3"><button onClick={reset} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!canSubmit || create.isPending} className="btn-primary gap-2">{create.isPending && <Loader2 size={15} className="animate-spin" />}Record</button></div>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load appointment records.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (data ?? []).length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400"><BriefcaseBusiness size={36} className="mb-3 opacity-40" /><p className="font-semibold">No appointment records yet</p></div>
      ) : (
        <div className="space-y-3">
          {data!.map((a) => (
            <div key={a.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="text-sm font-bold text-slate-900">{a.staff_name || "—"}</p>
                    <span className={cn("badge capitalize", TYPE_STYLE[a.appointment_type] || "")}>{typeLabel(a.appointment_type)}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">{a.title}{a.grade ? ` · ${a.grade}` : ""}{a.salary != null ? ` · ${naira(a.salary)}` : ""}</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">{a.effective_date ? `Effective ${formatDate(a.effective_date)}` : "No effective date"}{a.end_date ? ` → ${formatDate(a.end_date)}` : ""}{a.reference ? ` · ${a.reference}` : ""}</p>
                  {a.notes && <p className="text-sm text-slate-600 mt-2">{a.notes}</p>}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <select value={a.status} onChange={(e) => update.mutate({ id: a.id, data: { status: e.target.value } })} className={cn("text-xs font-semibold rounded-lg border px-2 py-1 capitalize", STATUS_STYLE[a.status] || "")}>
                    {["active", "ended"].map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <button onClick={() => { if (confirm("Delete this appointment record?")) del.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1"><Trash2 size={14} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
