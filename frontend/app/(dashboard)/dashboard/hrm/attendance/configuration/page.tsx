"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAttendanceSettings, useUpdateAttendanceSettings } from "@/hooks/useHrAttendance";
import { cn } from "@/lib/utils";
import { Settings2, Loader2, AlertTriangle, MapPin, Crosshair } from "lucide-react";

export default function AttendanceConfigPage() {
  const { data, isLoading, isError, refetch } = useAttendanceSettings();
  const update = useUpdateAttendanceSettings();
  const [f, setF] = useState({
    work_start_time: "", work_end_time: "", late_grace_minutes: "0",
    geofence_enabled: false, geofence_lat: "", geofence_lng: "", geofence_radius_m: "100",
  });

  useEffect(() => {
    if (data) setF({
      work_start_time: data.work_start_time?.slice(0, 5) ?? "",
      work_end_time: data.work_end_time?.slice(0, 5) ?? "",
      late_grace_minutes: String(data.late_grace_minutes ?? 0),
      geofence_enabled: data.geofence_enabled,
      geofence_lat: data.geofence_lat != null ? String(data.geofence_lat) : "",
      geofence_lng: data.geofence_lng != null ? String(data.geofence_lng) : "",
      geofence_radius_m: data.geofence_radius_m != null ? String(data.geofence_radius_m) : "100",
    });
  }, [data]);

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      setF((s) => ({ ...s, geofence_lat: pos.coords.latitude.toFixed(6), geofence_lng: pos.coords.longitude.toFixed(6) }));
    });
  };

  const save = () => update.mutate({
    work_start_time: f.work_start_time || null,
    work_end_time: f.work_end_time || null,
    late_grace_minutes: Number(f.late_grace_minutes) || 0,
    geofence_enabled: f.geofence_enabled,
    geofence_lat: f.geofence_lat ? Number(f.geofence_lat) : null,
    geofence_lng: f.geofence_lng ? Number(f.geofence_lng) : null,
    geofence_radius_m: f.geofence_radius_m ? Number(f.geofence_radius_m) : null,
  });

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><Link href="/dashboard/hrm/attendance/log" className="hover:text-brand-600">Access Control</Link><span>/</span><span className="text-brand-600 font-semibold">Configuration</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><Settings2 className="text-brand-600" size={22} /> Access Control Configuration</h1>
        <p className="text-slate-500 text-sm mt-0.5">Standard work hours, late-arrival grace, and where staff are allowed to clock in.</p>
      </div>

      {isLoading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-24 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center"><AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" /><p className="text-sm font-semibold text-slate-600">Couldn’t load settings.</p><button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button></div>
      ) : (
        <div className="space-y-4">
          {/* Work hours */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-sm font-bold text-slate-800 mb-3">Work hours</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div><label className="label">Start</label><input type="time" value={f.work_start_time} onChange={(e) => setF({ ...f, work_start_time: e.target.value })} className="input" /></div>
              <div><label className="label">End</label><input type="time" value={f.work_end_time} onChange={(e) => setF({ ...f, work_end_time: e.target.value })} className="input" /></div>
              <div><label className="label">Late grace (min)</label><input type="number" min={0} value={f.late_grace_minutes} onChange={(e) => setF({ ...f, late_grace_minutes: e.target.value })} className="input" /></div>
            </div>
            <p className="text-xs text-slate-400 mt-2">Clock-ins after start + grace are flagged “late”.</p>
          </div>

          {/* Geofencing */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-slate-800 flex items-center gap-2"><MapPin size={15} className="text-brand-600" /> Geofencing</h2>
              <button onClick={() => setF({ ...f, geofence_enabled: !f.geofence_enabled })} className={cn("text-[11px] font-bold uppercase tracking-wide px-2.5 py-1 rounded-full border", f.geofence_enabled ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-400 border-slate-200")}>
                {f.geofence_enabled ? "On" : "Off"}
              </button>
            </div>
            {f.geofence_enabled && (
              <>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                  <div><label className="label">Latitude</label><input value={f.geofence_lat} onChange={(e) => setF({ ...f, geofence_lat: e.target.value })} className="input" placeholder="6.5244" /></div>
                  <div><label className="label">Longitude</label><input value={f.geofence_lng} onChange={(e) => setF({ ...f, geofence_lng: e.target.value })} className="input" placeholder="3.3792" /></div>
                  <div><label className="label">Radius (m)</label><input type="number" min={10} value={f.geofence_radius_m} onChange={(e) => setF({ ...f, geofence_radius_m: e.target.value })} className="input" /></div>
                </div>
                <button onClick={useMyLocation} className="btn-secondary gap-1.5 mt-3 text-sm py-1.5"><Crosshair size={14} /> Use my current location</button>
                <p className="text-xs text-slate-400 mt-2">When on, staff must be within the radius (and share location) to clock in or out.</p>
              </>
            )}
          </div>

          <div className="flex justify-end">
            <button onClick={save} disabled={update.isPending} className="btn-primary gap-2">{update.isPending && <Loader2 size={15} className="animate-spin" />}Save settings</button>
          </div>
        </div>
      )}
    </div>
  );
}
