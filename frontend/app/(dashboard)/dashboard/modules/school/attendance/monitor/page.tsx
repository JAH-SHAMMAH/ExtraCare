"use client";

import { useState } from "react";
import { useAttendanceMonitor, type AttendanceMonitorCard } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";
import { Loader2, LogIn, LogOut, Users2, Clock, Radio, TrendingUp } from "lucide-react";

/**
 * School Live Attendance Monitor (Educare parity). A live campus-presence view
 * built on the check-in/out event backbone: how many students remain on-site, who
 * has departed, arrival timings, and the parent-arrivals (departures) feed.
 */
export default function AttendanceMonitorPage() {
  const { data, isLoading } = useAttendanceMonitor();
  const [tab, setTab] = useState<"live" | "arrivals">("live");

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="rounded-2xl bg-slate-900 text-white px-6 py-5 mb-6 flex items-start justify-between">
        <div>
          <p className="text-amber-400 font-black tabular-nums text-lg">{data?.date ?? "—"}</p>
          <h1 className="text-xl font-black tracking-tight">School Live Attendance Monitor</h1>
          <p className="text-slate-300 text-sm mt-0.5">Live overview of campus presence — who remains on-site and who has departed.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-400"><Radio size={13} /> Live</span>
      </div>

      {/* Headline stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl border-2 border-amber-200 p-5 text-center">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Students remaining in school</p>
          <p className="text-5xl font-black text-amber-500 tabular-nums mt-1">{isLoading ? "—" : data?.remaining ?? 0}</p>
        </div>
        <Stat icon={LogIn} label="Total Checked-in" value={data?.checked_in} tint="text-emerald-600" />
        <Stat icon={LogOut} label="Total Departed" value={data?.departed} tint="text-slate-600" />
        <div className="bg-white rounded-xl border border-slate-200 p-5 grid grid-cols-2 gap-3">
          <div><p className="text-[10px] font-bold uppercase text-slate-400 flex items-center gap-1"><Clock size={11} /> Min clock-in</p><p className="text-lg font-black text-slate-800 tabular-nums">{data?.min_clock_in ?? "—"}</p></div>
          <div><p className="text-[10px] font-bold uppercase text-slate-400 flex items-center gap-1"><TrendingUp size={11} /> Avg arrival</p><p className="text-lg font-black text-slate-800 tabular-nums">{data?.average_arrival ?? "—"}</p></div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 p-1 inline-flex mb-4">
        {[{ id: "live" as const, label: "Live Overview" }, { id: "arrivals" as const, label: "Parent Arrivals Log" }].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("px-4 py-1.5 text-xs font-bold rounded-lg transition-colors", tab === t.id ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100")}>{t.label}</button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>
      ) : tab === "live" ? (
        <StudentsInSchool cards={data?.students_in_school ?? []} />
      ) : (
        <ArrivalsLog recent={data?.recent ?? []} />
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, tint }: { icon: any; label: string; value?: number; tint: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
      <div className={cn("w-11 h-11 rounded-lg bg-slate-50 flex items-center justify-center", tint)}><Icon size={18} /></div>
      <div><p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p><p className={cn("text-3xl font-black tabular-nums", tint)}>{value ?? 0}</p></div>
    </div>
  );
}

function StudentsInSchool({ cards }: { cards: AttendanceMonitorCard[] }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-center gap-2 mb-4"><Users2 size={16} className="text-brand-600" /><h2 className="text-sm font-black text-slate-900">Students In School</h2><span className="text-xs text-slate-400">({cards.length})</span></div>
      {cards.length === 0 ? <p className="text-sm text-slate-400 py-6 text-center">No students currently on-site.</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {cards.map((c) => (
            <div key={c.student_id} className="rounded-xl border border-slate-100 p-3">
              <p className="text-sm font-bold text-slate-900">{c.student_name}</p>
              <p className="text-[11px] font-semibold text-brand-600 uppercase tracking-wide">{c.class_name || "—"}</p>
              {c.parent_name && <p className="text-xs text-slate-500 mt-1">Parent: {c.parent_name}</p>}
              {c.check_in && <p className="text-[11px] text-emerald-600 mt-1">In {c.check_in}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArrivalsLog({ recent }: { recent: Array<AttendanceMonitorCard & { type: "check_in" | "check_out"; late: boolean }> }) {
  const departures = recent.filter((r) => r.type === "check_out");
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100"><h2 className="text-sm font-black text-slate-900">Parent Arrivals / Departures</h2><p className="text-xs text-slate-400">Most recent check-outs (a parent arriving to collect a child).</p></div>
      {departures.length === 0 ? <p className="text-sm text-slate-400 py-8 text-center">No departures yet today.</p> : (
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Student", "Class", "Parent", "Departed", ""].map((h) => <th key={h} className="px-5 py-2.5 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {departures.map((r, i) => (
              <tr key={i} className={cn(r.late && "bg-rose-50/40")}>
                <td className="px-5 py-3 text-sm font-semibold text-slate-800">{r.student_name}</td>
                <td className="px-5 py-3 text-sm text-slate-600">{r.class_name || "—"}</td>
                <td className="px-5 py-3 text-xs text-slate-500">{r.parent_name || "—"}</td>
                <td className="px-5 py-3 text-sm tabular-nums text-slate-700">{r.check_out}</td>
                <td className="px-5 py-3">{r.late && <span className="badge bg-rose-50 text-rose-700 border-rose-200 text-[10px]">Late</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
