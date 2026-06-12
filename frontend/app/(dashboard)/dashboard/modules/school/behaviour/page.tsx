"use client";

import { useState } from "react";
import {
  useBehaviourRecords,
  useCreateBehaviourRecord,
  useDeleteBehaviourRecord,
} from "@/hooks/useSchoolExperience";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn, formatDate } from "@/lib/utils";
import { Smile, Frown, Meh, Plus, X, Loader2, Trash2 } from "lucide-react";
import type { BehaviourRecord, BehaviourType } from "@/types";

const TYPE_META: Record<BehaviourType, { label: string; icon: typeof Smile; tone: string }> = {
  positive: { label: "Positive", icon: Smile, tone: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  negative: { label: "Negative", icon: Frown, tone: "bg-rose-50 text-rose-700 border-rose-200" },
  neutral: { label: "Neutral", icon: Meh, tone: "bg-slate-50 text-slate-600 border-slate-200" },
};

export default function BehaviourPage() {
  const canWrite = useHasPermission("school:write");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [studentFilter, setStudentFilter] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data, isLoading } = useBehaviourRecords({
    type: typeFilter || undefined,
    student_id: studentFilter || undefined,
    page: 1,
    page_size: 50,
  });
  const createRecord = useCreateBehaviourRecord();
  const deleteRecord = useDeleteBehaviourRecord();

  const [form, setForm] = useState({
    student_id: "",
    type: "positive" as BehaviourType,
    category: "",
    description: "",
    points: 1,
    incident_date: new Date().toISOString().substring(0, 10),
  });

  const resetForm = () => {
    setForm({
      student_id: "", type: "positive", category: "",
      description: "", points: 1,
      incident_date: new Date().toISOString().substring(0, 10),
    });
    setShowForm(false);
  };

  const handleSubmit = () => {
    createRecord.mutate(
      { ...form, category: form.category || null },
      { onSuccess: resetForm },
    );
  };

  const records = data?.items as BehaviourRecord[] | undefined;

  const totals = records?.reduce(
    (acc, r) => {
      acc[r.type] = (acc[r.type] || 0) + 1;
      return acc;
    },
    {} as Record<BehaviourType, number>,
  );

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <span>Education</span><span>/</span>
            <span className="text-brand-600 font-semibold">Behaviour Tracker</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Pastoral &amp; Behaviour</h1>
          <p className="text-slate-500 text-sm mt-0.5">
            Record positive and negative behaviour incidents with merit points.
          </p>
        </div>
        {canWrite && (
          <button onClick={() => setShowForm(true)} className="btn-primary gap-2">
            <Plus size={15} />
            Record Incident
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Records", value: data?.total ?? "—" },
          { label: "Positive", value: totals?.positive ?? 0 },
          { label: "Negative", value: totals?.negative ?? 0 },
          { label: "Neutral", value: totals?.neutral ?? 0 },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">{label}</p>
            <p className="text-xl font-black text-slate-900">{value}</p>
          </div>
        ))}
      </div>

      {showForm && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold text-slate-800">New Behaviour Record</h2>
            <button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Student ID *</label>
              <input value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} className="input" />
            </div>
            <div>
              <label className="label">Type *</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as BehaviourType })} className="input">
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
                <option value="neutral">Neutral</option>
              </select>
            </div>
            <div>
              <label className="label">Category</label>
              <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="input" placeholder="Punctuality, Teamwork..." />
            </div>
            <div>
              <label className="label">Points</label>
              <input type="number" value={form.points} onChange={(e) => setForm({ ...form, points: Number(e.target.value) })} className="input" />
            </div>
            <div>
              <label className="label">Incident Date</label>
              <input type="date" value={form.incident_date} onChange={(e) => setForm({ ...form, incident_date: e.target.value })} className="input" />
            </div>
            <div className="md:col-span-2">
              <label className="label">Description *</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="input" rows={3} />
            </div>
          </div>
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={resetForm} className="btn-secondary">Cancel</button>
            <button onClick={handleSubmit} disabled={createRecord.isPending} className="btn-primary gap-2">
              {createRecord.isPending && <Loader2 size={15} className="animate-spin" />}
              Save Record
            </button>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 p-3 mb-4 flex flex-wrap items-center gap-3">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="input max-w-48">
          <option value="">All types</option>
          <option value="positive">Positive</option>
          <option value="negative">Negative</option>
          <option value="neutral">Neutral</option>
        </select>
        <input
          value={studentFilter}
          onChange={(e) => setStudentFilter(e.target.value)}
          placeholder="Filter by student ID"
          className="input flex-1 min-w-48"
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                {["Type", "Student", "Category", "Description", "Points", "Date", ""].map((h) => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {isLoading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-4"><div className="h-4 bg-slate-100 rounded animate-pulse w-24" /></td>
                    ))}
                  </tr>
                ))
              ) : records && records.length > 0 ? (
                records.map((r) => {
                  const meta = TYPE_META[r.type];
                  const Icon = meta.icon;
                  return (
                    <tr key={r.id} className="hover:bg-slate-50/70">
                      <td className="px-5 py-4">
                        <span className={cn("badge border inline-flex items-center gap-1", meta.tone)}>
                          <Icon size={11} />
                          {meta.label}
                        </span>
                      </td>
                      <td className="px-5 py-4"><span className="text-xs font-mono text-slate-600">{r.student_id.slice(0, 8)}</span></td>
                      <td className="px-5 py-4"><span className="text-sm text-slate-600">{r.category || "—"}</span></td>
                      <td className="px-5 py-4 max-w-xs"><p className="text-sm text-slate-700 line-clamp-2">{r.description}</p></td>
                      <td className="px-5 py-4">
                        <span className={cn(
                          "text-sm font-bold",
                          r.points > 0 ? "text-emerald-600" : r.points < 0 ? "text-rose-600" : "text-slate-500",
                        )}>
                          {r.points > 0 ? "+" : ""}{r.points}
                        </span>
                      </td>
                      <td className="px-5 py-4"><span className="text-xs text-slate-500">{formatDate(r.incident_date)}</span></td>
                      <td className="px-5 py-4">
                        {canWrite && (
                          <button
                            onClick={() => { if (confirm("Delete this record?")) deleteRecord.mutate(r.id); }}
                            className="text-slate-400 hover:text-red-600 p-1"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-slate-400">
                    <Smile size={36} className="mx-auto mb-3 opacity-40" />
                    <p className="font-semibold">No behaviour records yet</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
