"use client";

import { useState } from "react";
import {
  useWeeklyRemarks,
  useCreateRemark,
  useDeleteRemark,
} from "@/hooks/useSchoolExperience";
import { useMineFilter } from "@/hooks/useMineFilter";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { formatDate } from "@/lib/utils";
import { MessageCircle, Plus, X, Loader2, Trash2, User } from "lucide-react";
import type { WeeklyRemark } from "@/types";

function getMonday(d: Date) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
}

export default function WeeklyRemarksPage() {
  const canWrite = useHasPermission("school:write");
  const { mine, setMine } = useMineFilter();
  const [studentFilter, setStudentFilter] = useState("");
  const [weekFilter, setWeekFilter] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading } = useWeeklyRemarks({
    student_id: studentFilter || undefined,
    week_start: weekFilter || undefined,
    for_me: mine || undefined,
  });
  const createRemark = useCreateRemark();
  const deleteRemark = useDeleteRemark();

  const [form, setForm] = useState({
    student_id: "",
    teacher_id: "",
    week_start: getMonday(new Date()).toISOString().substring(0, 10),
    remark: "",
    strengths: "",
    areas_to_improve: "",
  });

  const resetForm = () => {
    setForm({
      student_id: "", teacher_id: "",
      week_start: getMonday(new Date()).toISOString().substring(0, 10),
      remark: "", strengths: "", areas_to_improve: "",
    });
    setShowForm(false);
  };

  const handleSubmit = () => {
    createRemark.mutate(
      {
        ...form,
        strengths: form.strengths || null,
        areas_to_improve: form.areas_to_improve || null,
      },
      { onSuccess: resetForm },
    );
  };

  const remarks = data as WeeklyRemark[] | undefined;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Weekly Remarks</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Weekly Remarks</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Teacher feedback on each student's weekly progress.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setShowForm(true)} className="btn-primary gap-2">
            <Plus size={15} />
            New Remark
          </button>
        )}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Weekly Remark</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Student ID *</label>
              <input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Teacher ID *</label>
              <input value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Week Start (Monday) *</label>
              <input type="date" value={form.week_start} onChange={(e) => setForm({ ...form, week_start: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Remark *</label>
              <textarea value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} className="input" rows={3} />
            </div>
            <div>
              <label className="label">Strengths</label>
              <textarea value={form.strengths} onChange={(e) => setForm({ ...form, strengths: e.target.value })} className="input" rows={2} />
            </div>
            <div>
              <label className="label">Areas to Improve</label>
              <textarea value={form.areas_to_improve} onChange={(e) => setForm({ ...form, areas_to_improve: e.target.value })} className="input" rows={2} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createRemark.isPending} className="btn-primary gap-2">
              {createRemark.isPending && <Loader2 size={15} className="animate-spin" />}
              Save Remark
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <input
          value={studentFilter}
          onChange={(e) => setStudentFilter(e.target.value)}
          placeholder="Filter by student ID"
          className="input flex-1 min-w-48"
        />
        <input
          type="date"
          value={weekFilter}
          onChange={(e) => setWeekFilter(e.target.value)}
          className="input max-w-48"
        />
        {mine && (
          <button
            onClick={() => setMine(false)}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-brand-700 bg-brand-50 border border-brand-200 rounded-lg px-3 py-1.5 hover:bg-brand-100"
          >
            Showing: Mine
            <X size={12} />
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 bg-slate-100 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : remarks && remarks.length > 0 ? (
        <div className="space-y-3">
          {remarks.map((r) => (
            <div key={r.id} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                    <User size={13} className="text-slate-400" />
                    Student {r.student_id.slice(0, 8)}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Week of {formatDate(r.week_start)} · Teacher {r.teacher_id.slice(0, 8)}
                  </p>
                </div>
                {canWrite && (
                  <button
                    onClick={() => { if (confirm("Delete this remark?")) deleteRemark.mutate(r.id); }}
                    className="text-slate-400 hover:text-red-600 p-1"
                  >
                    <Trash2 size={13} />
                  </button>
                )}
              </div>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{r.remark}</p>
              {(r.strengths || r.areas_to_improve) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
                  {r.strengths && (
                    <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
                      <p className="text-[10px] font-bold uppercase text-emerald-700 mb-1">Strengths</p>
                      <p className="text-sm text-slate-700">{r.strengths}</p>
                    </div>
                  )}
                  {r.areas_to_improve && (
                    <div className="bg-amber-50 border border-amber-100 rounded-lg p-3">
                      <p className="text-[10px] font-bold uppercase text-amber-700 mb-1">Areas to Improve</p>
                      <p className="text-sm text-slate-700">{r.areas_to_improve}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <MessageCircle size={36} className="mb-3 opacity-40" />
          <p className="font-semibold">No weekly remarks yet</p>
        </div>
      )}
    </div>
  );
}
