"use client";

import { useState } from "react";
import { useStaff } from "@/hooks/useUsers";
import {
  useStaffAttendanceLog, useAddAttendanceEvent, useDeleteAttendanceEvent, type AttendanceEvent,
} from "@/hooks/useHrAttendance";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Fingerprint, Plus, Loader2, Trash2, AlertTriangle, LogIn, LogOut, Lock } from "lucide-react";

const dt = (iso: string) => new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export default function ClockLogPage() {
  const canWrite = useHasPermission("hr:write");
  const [staffId, setStaffId] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const { data, isLoading, isError, refetch } = useStaffAttendanceLog({
    staff_user_id: staffId || undefined, from_date: from || undefined, to_date: to || undefined,
  });
  const { data: staff } = useStaff();
  const add = useAddAttendanceEvent();
  const del = useDeleteAttendanceEvent();
  const [show, setShow] = useState(false);
  const [f, setF] = useState({ staff_user_id: "", event_type: "clock_in", event_time: "", note: "" });
  const reset = () => { setF({ staff_user_id: "", event_type: "clock_in", event_time: "", note: "" }); setShow(false); };
  const staffList: any[] = (staff as any[]) ?? [];
  const rows = data ?? [];

  const submit = () => {
    if (!f.staff_user_id) return;
    add.mutate(
      { staff_user_id: f.staff_user_id, event_type: f.event_type, event_time: f.event_time ? new Date(f.event_time).toISOString() : undefined, note: f.note || undefined },
      { onSuccess: reset },
    );
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">Clock Log</span></nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">Clock In / Out Log</h1>
          <p className="text-slate-500 text-sm mt-0.5">Staff attendance punches. Add or correct entries as needed.</p>
        </div>
        {canWrite && <button onClick={() => { reset(); setShow(true); }} className="btn-primary gap-2"><Plus size={15} /> Add Punch</button>}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <select value={staffId} onChange={(e) => setStaffId(e.target.value)} className="input max-w-[220px]">
          <option value="">All staff</option>
          {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
        </select>
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="input max-w-[160px]" title="From" />
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="input max-w-[160px]" title="To" />
      </div>

      {show && canWrite && (
        <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap gap-2 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="label">Staff *</label>
            <select value={f.staff_user_id} onChange={(e) => setF({ ...f, staff_user_id: e.target.value })} className="input">
              <option value="">Select…</option>
              {staffList.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
            </select>
          </div>
          <div className="min-w-[130px]"><label className="label">Type</label>
            <select value={f.event_type} onChange={(e) => setF({ ...f, event_type: e.target.value })} className="input">
              <option value="clock_in">Clock In</option><option value="clock_out">Clock Out</option>
            </select>
          </div>
          <div className="min-w-[190px]"><label className="label">When</label><input type="datetime-local" value={f.event_time} onChange={(e) => setF({ ...f, event_time: e.target.value })} className="input" /></div>
          <div className="flex-1 min-w-[150px]"><label className="label">Note</label><input value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} className="input" placeholder="Optional" /></div>
          <button onClick={submit} disabled={!f.staff_user_id || add.isPending} className="btn-primary gap-1.5">{add.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />} Add</button>
          <button onClick={reset} className="btn-secondary">Cancel</button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-12 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load the log.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Fingerprint size={34} className="mb-3 opacity-40" /><p className="font-semibold">No punches recorded</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {rows.map((e: AttendanceEvent) => (
            <div key={e.id} className="flex items-center gap-3 px-4 py-3">
              <span className={cn("inline-flex items-center gap-1 text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded-full border shrink-0",
                e.event_type === "clock_in" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-500 border-slate-200")}>
                {e.event_type === "clock_in" ? <LogIn size={11} /> : <LogOut size={11} />}{e.event_type === "clock_in" ? "In" : "Out"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800 truncate">{e.staff_name || "—"}</p>
                <p className="text-xs text-slate-400 truncate">{dt(e.event_time)}{e.note ? ` · ${e.note}` : ""}{e.source !== "manual" ? ` · ${e.source}` : ""}</p>
              </div>
              {canWrite && <button onClick={() => { if (confirm("Remove this punch?")) del.mutate(e.id); }} className="text-slate-400 hover:text-red-600 p-1.5" title="Remove"><Trash2 size={14} /></button>}
            </div>
          ))}
        </div>
      )}

      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><Lock size={12} /> The clock log is HR-admin only (hr:write).</p>}
    </div>
  );
}
