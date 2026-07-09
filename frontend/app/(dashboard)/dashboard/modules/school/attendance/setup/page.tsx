"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  useAttendanceSettings, useUpdateAttendanceSettings,
  useAbsenceReasons, useCreateAbsenceReason, useUpdateAbsenceReason, useDeleteAbsenceReason,
} from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { Clock, ListChecks, Plus, Loader2, ArrowLeft, Save, Trash2, ShieldCheck, ShieldAlert } from "lucide-react";

interface Reason { id: string; code: string; label: string; is_authorized: boolean; is_active: boolean; }

export default function AttendanceSetupPage() {
  const canWrite = useHasPermission("settings:write");
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <Link href="/dashboard/modules/school/attendance" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 mb-4"><ArrowLeft size={13} /> Attendance</Link>
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Attendance</span><span>/</span><span className="text-brand-600 font-semibold">Setup</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Attendance Setup</h1>
        <p className="text-slate-500 text-sm mt-0.5">The late cutoff applied when check-ins are recorded, and the reason codes staff pick when marking an absence.</p>
      </div>

      <LateCutoff canWrite={canWrite} />
      <AbsenceReasons canWrite={canWrite} />

      {!canWrite && <p className="text-xs text-slate-400 mt-4 flex items-center gap-1"><ShieldAlert size={12} /> Editing attendance setup requires the settings:write capability.</p>}
    </div>
  );
}

function LateCutoff({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useAttendanceSettings();
  const save = useUpdateAttendanceSettings();
  const [time, setTime] = useState("08:00");

  useEffect(() => { if (data?.late_after_time) setTime(data.late_after_time); }, [data]);

  return (
    <section className="bg-white rounded-xl border border-slate-200 p-6 mb-5">
      <div className="flex items-center gap-2 mb-1"><Clock size={16} className="text-brand-600" /><h2 className="text-sm font-bold text-slate-800">Late cutoff</h2></div>
      <p className="text-xs text-slate-500 mb-4">A check-in at or after this local time is recorded as <span className="font-semibold text-amber-700">Late</span>; earlier check-ins are Present.</p>
      {isLoading ? (
        <div className="h-9 w-40 bg-slate-100 rounded animate-pulse" />
      ) : (
        <div className="flex items-end gap-3">
          <div><label className="label">Late after</label><input type="time" value={time} onChange={(e) => setTime(e.target.value)} disabled={!canWrite} className="input w-40" /></div>
          {canWrite && (
            <button onClick={() => save.mutate({ late_after_time: time })} disabled={save.isPending || time === data?.late_after_time} className="btn-primary gap-2">
              {save.isPending ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />} Save
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function AbsenceReasons({ canWrite }: { canWrite: boolean }) {
  const { data, isLoading } = useAbsenceReasons(false);
  const create = useCreateAbsenceReason();
  const update = useUpdateAbsenceReason();
  const del = useDeleteAbsenceReason();
  const reasons: Reason[] = data || [];

  const [label, setLabel] = useState("");
  const [authorized, setAuthorized] = useState(true);

  const add = () => {
    if (!label.trim()) return;
    create.mutate({ code: label.trim().toLowerCase().replace(/\s+/g, "_"), label: label.trim(), is_authorized: authorized },
      { onSuccess: () => { setLabel(""); setAuthorized(true); } });
  };

  return (
    <section className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex items-center gap-2 mb-1"><ListChecks size={16} className="text-brand-600" /><h2 className="text-sm font-bold text-slate-800">Absence reasons</h2></div>
      <p className="text-xs text-slate-500 mb-4">Reason codes shown when a student is marked absent or late. Deactivate a reason to retire it without losing history; reasons in use can’t be deleted.</p>

      {canWrite && (
        <div className="flex items-end gap-2 mb-5 flex-wrap">
          <div className="flex-1 min-w-[180px]"><label className="label">New reason</label><input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Sports fixture" className="input" onKeyDown={(e) => e.key === "Enter" && add()} /></div>
          <label className="flex items-center gap-2 text-sm text-slate-600 pb-2.5 cursor-pointer"><input type="checkbox" checked={authorized} onChange={(e) => setAuthorized(e.target.checked)} className="w-4 h-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />Authorised</label>
          <button onClick={add} disabled={create.isPending || !label.trim()} className="btn-primary gap-2">{create.isPending ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}Add</button>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-11 bg-slate-100 rounded-lg animate-pulse" />)}</div>
      ) : (
        <div className="divide-y divide-slate-100 border border-slate-100 rounded-lg">
          {reasons.map((r) => (
            <div key={r.id} className={cn("flex items-center gap-3 px-4 py-2.5", !r.is_active && "opacity-50")}>
              <span className={cn("badge inline-flex items-center gap-1", r.is_authorized ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200")}>
                {r.is_authorized ? <ShieldCheck size={11} /> : <ShieldAlert size={11} />}{r.is_authorized ? "Authorised" : "Unauthorised"}
              </span>
              <span className="text-sm font-medium text-slate-800 flex-1">{r.label}</span>
              {canWrite && (
                <div className="flex items-center gap-3">
                  <button onClick={() => update.mutate({ id: r.id, data: { is_authorized: !r.is_authorized } })} className="text-xs text-slate-400 hover:text-slate-700">Toggle</button>
                  <button onClick={() => update.mutate({ id: r.id, data: { is_active: !r.is_active } })} className="text-xs font-semibold text-slate-500 hover:underline">{r.is_active ? "Deactivate" : "Reactivate"}</button>
                  <button onClick={() => del.mutate(r.id)} disabled={del.isPending} className="text-slate-400 hover:text-rose-600" title="Delete (only if unused)"><Trash2 size={14} /></button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
