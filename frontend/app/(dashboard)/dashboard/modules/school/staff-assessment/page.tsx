"use client";

import { useState } from "react";
import {
  useStaffAssessments, useCreateAssessment, useUpdateAssessment, useDeleteAssessment,
} from "@/hooks/usePeople";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { EntityPicker } from "@/components/inputs/EntityPicker";
import { cn, formatDate } from "@/lib/utils";
import {
  ClipboardList, Plus, X, Loader2, Edit2, Trash2, AlertTriangle, Star,
} from "lucide-react";
import type { StaffAssessment } from "@/types";

const STATUSES = ["draft", "finalized"];

const EMPTY = {
  staff_user_id: "", period: "", review_date: "", overall_rating: "",
  strengths: "", improvements: "", goals: "", status: "draft",
};

export default function StaffAssessmentPage() {
  const canWrite = useHasPermission("hr:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<StaffAssessment | null>(null);
  const [form, setForm] = useState({ ...EMPTY });

  const { data, isLoading, isError, refetch } = useStaffAssessments(
    statusFilter ? { status: statusFilter } : undefined,
  );
  const createA = useCreateAssessment();
  const updateA = useUpdateAssessment();
  const deleteA = useDeleteAssessment();

  const reset = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(false); };

  const openNew = () => { setForm({ ...EMPTY }); setEditing(null); setShowForm(true); };
  const openEdit = (a: StaffAssessment) => {
    setForm({
      staff_user_id: a.staff_user_id,
      period: a.period,
      review_date: a.review_date ?? "",
      overall_rating: a.overall_rating?.toString() ?? "",
      strengths: a.strengths ?? "",
      improvements: a.improvements ?? "",
      goals: a.goals ?? "",
      status: a.status,
    });
    setEditing(a);
    setShowForm(true);
  };

  const submit = () => {
    const payload: Record<string, unknown> = {
      period: form.period,
      review_date: form.review_date || null,
      overall_rating: form.overall_rating ? Number(form.overall_rating) : null,
      strengths: form.strengths || null,
      improvements: form.improvements || null,
      goals: form.goals || null,
      status: form.status,
    };
    if (editing) {
      updateA.mutate({ id: editing.id, data: payload }, { onSuccess: reset });
    } else {
      payload.staff_user_id = form.staff_user_id.trim();
      createA.mutate(payload, { onSuccess: reset });
    }
  };

  const rows = data?.items;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>People &amp; HR</span><span>/</span>
            <span className="text-brand-600 font-semibold">Staff Assessment</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Staff Assessment</h1>
          <p className="text-slate-500 text-sm mt-0.5">Performance appraisals and development goals.</p>
        </div>
        {canWrite && (
          <button onClick={openNew} className="btn-primary gap-2"><Plus size={15} /> New Assessment</button>
        )}
      </div>

      <div className="mb-5">
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">{editing ? "Edit Assessment" : "New Assessment"}</h2>
            <button onClick={reset} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {!editing && (
              <div>
                <label className="label">Staff Member *</label>
                <EntityPicker
                  type="staff"
                  value={form.staff_user_id || null}
                  onChange={(id) => setForm({ ...form, staff_user_id: id || "" })}
                />
              </div>
            )}
            <div>
              <label className="label">Review Period *</label>
              <input value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="input" placeholder="e.g. 2025/2026 Term 1" />
            </div>
            <div>
              <label className="label">Review Date</label>
              <input type="date" value={form.review_date} onChange={(e) => setForm({ ...form, review_date: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Overall Rating</label>
              <select value={form.overall_rating} onChange={(e) => setForm({ ...form, overall_rating: e.target.value })} className="input">
                <option value="">—</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n} / 5</option>)}
              </select>
            </div>
            <div>
              <label className="label">Status</label>
              <select value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })} className="input capitalize">
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="label">Strengths</label>
              <textarea value={form.strengths} onChange={(e) => setForm({ ...form, strengths: e.target.value })} className="input" rows={2} />
            </div>
            <div className="md:col-span-2">
              <label className="label">Areas for Improvement</label>
              <textarea value={form.improvements} onChange={(e) => setForm({ ...form, improvements: e.target.value })} className="input" rows={2} />
            </div>
            <div className="md:col-span-2">
              <label className="label">Goals</label>
              <textarea value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} className="input" rows={2} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={reset} className="btn-secondary">Cancel</button>
            <button
              onClick={submit}
              disabled={(!editing && !form.staff_user_id.trim()) || !form.period.trim() || createA.isPending || updateA.isPending}
              className="btn-primary gap-2"
            >
              {(createA.isPending || updateA.isPending) && <Loader2 size={15} className="animate-spin" />}
              {editing ? "Update" : "Create"}
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Staff", "Period", "Rating", "Status", "Reviewer", "Date", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i}>{Array.from({ length: 7 }).map((_, j) => (
                  <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-20" /></td>
                ))}</tr>
              ))
            ) : isError ? (
              <tr>
                <td colSpan={7} className="py-14 text-center">
                  <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
                  <p className="text-sm font-semibold text-slate-600">Couldn’t load assessments.</p>
                  <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
                </td>
              </tr>
            ) : rows && rows.length > 0 ? (
              rows.map((a) => (
                <tr key={a.id} className="hover:bg-slate-50/70">
                  <td className="px-5 py-4"><span className="text-sm font-semibold text-slate-800">{a.staff_name || a.staff_user_id.slice(0, 8)}</span></td>
                  <td className="px-5 py-4"><span className="text-sm text-slate-600">{a.period}</span></td>
                  <td className="px-5 py-4">
                    {a.overall_rating ? (
                      <span className="inline-flex items-center gap-1 text-sm text-slate-700">
                        <Star size={13} className="text-amber-500" fill="currentColor" /> {a.overall_rating}/5
                      </span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-5 py-4">
                    <span className={cn("badge capitalize", a.status === "finalized"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-slate-50 text-slate-500 border-slate-200")}>
                      {a.status}
                    </span>
                  </td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{a.reviewer_name || "—"}</span></td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{a.review_date ? formatDate(a.review_date) : "—"}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1">
                        <button onClick={() => openEdit(a)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                        <button onClick={() => { if (confirm("Delete this assessment?")) deleteA.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-16 text-center text-slate-400">
                  <ClipboardList size={36} className="mx-auto mb-3 opacity-40" />
                  <p className="font-semibold">No assessments yet</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
