"use client";

import { useState } from "react";
import Link from "next/link";
import { useStaffAssessments, useDeleteAssessment, useUpdateAssessment } from "@/hooks/usePeople";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { AssessmentForm } from "../AssessmentForm";
import { cn, formatDate } from "@/lib/utils";
import { ClipboardList, X, Edit2, Trash2, AlertTriangle, Star, CheckCircle2, ArrowLeft } from "lucide-react";
import type { StaffAssessment } from "@/types";

const STATUSES = ["draft", "finalized"];

export default function ManageAssessmentsPage() {
  const canWrite = useHasPermission("hr:write");
  const [statusFilter, setStatusFilter] = useState("");
  const [editing, setEditing] = useState<StaffAssessment | null>(null);

  const { data, isLoading, isError, refetch } = useStaffAssessments(statusFilter ? { status: statusFilter } : undefined);
  const del = useDeleteAssessment();
  const update = useUpdateAssessment();
  const rows = data?.items;

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <Link href="/dashboard/modules/school/staff-assessment" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Staff Assessment</Link>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Staff Management</span><span>/</span><span className="text-brand-600 font-semibold">Manage Staff Assessment</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Staff Assessment</h1>
          <p className="text-slate-500 text-sm mt-0.5">Review, edit, finalize and remove appraisals.</p>
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input max-w-[180px] capitalize">
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100">
              {["Staff", "Period", "Rating", "Status", "Reviewer", "Date", ""].map((h) => (
                <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
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
                      <span className="inline-flex items-center gap-1 text-sm text-slate-700"><Star size={13} className="text-amber-500" fill="currentColor" /> {a.overall_rating}/5</span>
                    ) : <span className="text-slate-300">—</span>}
                  </td>
                  <td className="px-5 py-4">
                    <span className={cn("badge capitalize", a.status === "finalized" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-50 text-slate-500 border-slate-200")}>{a.status}</span>
                  </td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{a.reviewer_name || "—"}</span></td>
                  <td className="px-5 py-4"><span className="text-xs text-slate-500">{a.review_date ? formatDate(a.review_date) : "—"}</span></td>
                  <td className="px-5 py-4">
                    {canWrite && (
                      <div className="flex items-center gap-1">
                        {a.status !== "finalized" && (
                          <button onClick={() => update.mutate({ id: a.id, data: { status: "finalized" } })} className="text-slate-400 hover:text-emerald-600 p-1" title="Finalize"><CheckCircle2 size={14} /></button>
                        )}
                        <button onClick={() => setEditing(a)} className="text-slate-400 hover:text-brand-600 p-1" title="Edit"><Edit2 size={14} /></button>
                        <button onClick={() => { if (confirm("Delete this assessment?")) del.mutate(a.id); }} className="text-slate-400 hover:text-red-600 p-1" title="Delete"><Trash2 size={14} /></button>
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

      {editing && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={() => setEditing(null)}>
          <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between p-5 border-b border-slate-100">
              <h2 className="text-base font-bold text-slate-900">Edit assessment · {editing.staff_name || ""}</h2>
              <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-slate-600"><X size={18} /></button>
            </div>
            <div className="p-5">
              <AssessmentForm initial={editing} onDone={() => setEditing(null)} onCancel={() => setEditing(null)} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
