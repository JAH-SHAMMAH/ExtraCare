"use client";

import { useState } from "react";
import { useTimetable, useCreateTimetableSlot } from "@/hooks/useSchool";
import { Calendar, Plus, X, Loader2, AlertTriangle } from "lucide-react";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { getApiErrorMessage } from "@/lib/utils";

const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"] as const;
// Backend stores day_of_week as 0=Monday..6=Sunday. This mapping is how we
// align API rows with the grid without changing the DB schema.
const DAY_TO_INDEX: Record<(typeof DAYS)[number], number> = {
  monday: 0,
  tuesday: 1,
  wednesday: 2,
  thursday: 3,
  friday: 4,
};
const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8];

// Narrow, defensive shape — we only rely on what the backend actually sends.
// Anything extra (class_name, subject_name) is optional and safely stringified
// at render time.
type BackendTimetableRow = {
  id: string;
  class_id: string;
  subject_id: string;
  teacher_id: string | null;
  day_of_week: number;
  start_time: string;
  end_time: string;
  room: string | null;
  subject_name?: unknown;
  teacher_name?: unknown;
};

function toText(value: unknown, fallback = ""): string {
  if (value == null) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

export default function TimetablePage() {
  return (
    <ErrorBoundary>
      <TimetablePageInner />
    </ErrorBoundary>
  );
}

function TimetablePageInner() {
  const [classId, setClassId] = useState("");
  const [showForm, setShowForm] = useState(false);
  const { data, isLoading, error } = useTimetable({ class_id: classId || undefined });
  const createSlot = useCreateTimetableSlot();
  const [form, setForm] = useState({ class_id: "", subject_id: "", teacher_id: "", day: "monday", period: "1", start_time: "08:00", end_time: "08:45" });
  const resetForm = () => { setForm({ class_id: classId, subject_id: "", teacher_id: "", day: "monday", period: "1", start_time: "08:00", end_time: "08:45" }); setShowForm(false); };
  const handleSubmit = () => {
    // Translate the form's day label into the backend integer the API expects.
    const payload = {
      class_id: classId || form.class_id,
      subject_id: form.subject_id,
      teacher_id: form.teacher_id || null,
      day_of_week: DAY_TO_INDEX[form.day as keyof typeof DAY_TO_INDEX] ?? 0,
      start_time: form.start_time,
      end_time: form.end_time,
    };
    createSlot.mutate(payload, { onSuccess: resetForm });
  };

  const rawList = (data as { items?: unknown })?.items;
  const slots: BackendTimetableRow[] = Array.isArray(rawList)
    ? (rawList as BackendTimetableRow[])
    : Array.isArray(data)
    ? (data as BackendTimetableRow[])
    : [];

  const getSlot = (day: (typeof DAYS)[number], period: number) => {
    const dayIdx = DAY_TO_INDEX[day];
    // The API doesn't store a period index — match by slot order within the day.
    const perDay = slots
      .filter((s) => s.day_of_week === dayIdx)
      .sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""));
    return perDay[period - 1];
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-8 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Timetable</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Class Timetable</h1>
          <p className="text-slate-500 text-sm mt-0.5">View and manage weekly class schedules.</p>
        </div>
        <button onClick={() => { resetForm(); setShowForm(true); }} className="btn-primary gap-2"><Plus size={15} /> Add Slot</button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex items-end gap-4">
        <div><label className="label">Class ID</label><input value={classId} onChange={(e) => setClassId(e.target.value)} placeholder="Enter class ID..." className="input w-64" /></div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 flex items-start gap-2">
          <AlertTriangle size={16} className="text-rose-500 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-rose-700">
            {getApiErrorMessage(error, "Could not load timetable.")}
          </p>
        </div>
      )}

      {showForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-center justify-between mb-4"><h2 className="text-sm font-bold text-slate-800">Add Timetable Slot</h2><button onClick={resetForm} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div><label className="label">Day</label><select value={form.day} onChange={(e) => setForm({ ...form, day: e.target.value })} className="input">{DAYS.map((d) => (<option key={d} value={d} className="capitalize">{d.charAt(0).toUpperCase() + d.slice(1)}</option>))}</select></div>
            <div><label className="label">Period</label><select value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} className="input">{PERIODS.map((p) => (<option key={p} value={p}>Period {p}</option>))}</select></div>
            <div><label className="label">Subject ID</label><input value={form.subject_id} onChange={(e) => setForm({ ...form, subject_id: e.target.value })} className="input" /></div>
            <div><label className="label">Teacher ID</label><input value={form.teacher_id} onChange={(e) => setForm({ ...form, teacher_id: e.target.value })} className="input" /></div>
            <div><label className="label">Start Time</label><input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} className="input" /></div>
            <div><label className="label">End Time</label><input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} className="input" /></div>
          </div>
          <div className="flex justify-end gap-3 mt-4"><button onClick={resetForm} className="btn-secondary">Cancel</button><button onClick={handleSubmit} disabled={createSlot.isPending} className="btn-primary gap-2">{createSlot.isPending && <Loader2 size={15} className="animate-spin" />}Add Slot</button></div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {isLoading ? (<div className="p-12 text-center"><Loader2 size={24} className="animate-spin text-slate-400 mx-auto" /></div>) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead><tr className="bg-slate-50/80 border-b border-slate-100">
                <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 w-20">Period</th>
                {DAYS.map((d) => (<th key={d} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 capitalize">{d}</th>))}
              </tr></thead>
              <tbody className="divide-y divide-slate-50">
                {PERIODS.map((period) => (
                  <tr key={period} className="hover:bg-slate-50/30">
                    <td className="px-4 py-3 text-xs font-bold text-slate-500">{period}</td>
                    {DAYS.map((day) => {
                      const slot = getSlot(day, period);
                      return (
                        <td key={day} className="px-4 py-3">
                          {slot ? (
                            <div className="bg-brand-50 rounded-lg p-2 border border-brand-100">
                              <p className="text-xs font-bold text-brand-700">
                                {toText(slot.subject_name, toText(slot.subject_id, "—"))}
                              </p>
                              <p className="text-[10px] text-brand-500">
                                {toText(slot.teacher_name, toText(slot.teacher_id, ""))}
                              </p>
                              <p className="text-[10px] text-slate-400">{slot.start_time}–{slot.end_time}</p>
                            </div>
                          ) : (
                            <div className="h-14 rounded-lg border-2 border-dashed border-slate-100 flex items-center justify-center">
                              <span className="text-[10px] text-slate-300">—</span>
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && !classId && (
          <div className="p-12 text-center text-slate-400"><Calendar size={32} className="mx-auto mb-2 opacity-50" /><p className="text-sm">Enter a Class ID to view the timetable.</p></div>
        )}
      </div>
    </div>
  );
}
