"use client";

import { useMyAttendance, useClock, type AttendanceEvent } from "@/hooks/useHrAttendance";
import { cn } from "@/lib/utils";
import { LogIn, LogOut, Clock, AlertTriangle, CalendarDays } from "lucide-react";

const dayKey = (iso: string) => new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

type Day = { label: string; firstIn?: string; lastOut?: string; count: number };

function groupByDay(events: AttendanceEvent[]): Day[] {
  const map = new Map<string, AttendanceEvent[]>();
  for (const e of events) {
    const k = dayKey(e.event_time);
    if (!map.has(k)) map.set(k, []);
    map.get(k)!.push(e);
  }
  return Array.from(map.entries()).map(([label, evs]) => {
    const ins = evs.filter((e) => e.event_type === "clock_in").map((e) => e.event_time).sort();
    const outs = evs.filter((e) => e.event_type === "clock_out").map((e) => e.event_time).sort();
    return { label, firstIn: ins[0], lastOut: outs[outs.length - 1], count: evs.length };
  });
}

const hours = (a?: string, b?: string) =>
  a && b ? Math.max(0, (new Date(b).getTime() - new Date(a).getTime()) / 3.6e6).toFixed(1) : null;

export default function MyAttendancePage() {
  const { data, isLoading, isError, refetch } = useMyAttendance();
  const clock = useClock();
  const events = data ?? [];
  const days = groupByDay(events);
  // Currently clocked in if the most recent event today is a clock_in.
  const today = dayKey(new Date().toISOString());
  const todayEvents = events.filter((e) => dayKey(e.event_time) === today);
  const clockedIn = todayEvents.length > 0 && todayEvents[0].event_type === "clock_in";

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>HR Manager</span><span>/</span><span className="text-brand-600 font-semibold">My Attendance</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Attendance</h1>
        <p className="text-slate-500 text-sm mt-0.5">Clock in and out, and review your attendance history.</p>
      </div>

      {/* Clock panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className={cn("w-2.5 h-2.5 rounded-full", clockedIn ? "bg-emerald-500 animate-pulse" : "bg-slate-300")} />
          <div>
            <p className="text-sm font-bold text-slate-800">{clockedIn ? "You’re clocked in" : "You’re clocked out"}</p>
            <p className="text-xs text-slate-400">{todayEvents.length > 0 ? `Last: ${hhmm(todayEvents[0].event_time)} today` : "No punches yet today"}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => clock.mutate({ event_type: "clock_in" })} disabled={clock.isPending || clockedIn}
            className="btn-primary gap-1.5 disabled:opacity-40"><LogIn size={15} /> Clock In</button>
          <button onClick={() => clock.mutate({ event_type: "clock_out" })} disabled={clock.isPending || !clockedIn}
            className="btn-secondary gap-1.5 disabled:opacity-40"><LogOut size={15} /> Clock Out</button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">{Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 rounded-xl animate-pulse" />)}</div>
      ) : isError ? (
        <div className="bg-white rounded-xl border border-slate-200 py-14 text-center">
          <AlertTriangle size={28} className="mx-auto mb-3 text-amber-400" />
          <p className="text-sm font-semibold text-slate-600">Couldn’t load your attendance.</p>
          <button onClick={() => refetch()} className="mt-3 btn-secondary">Retry</button>
        </div>
      ) : days.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400">
          <Clock size={34} className="mb-3 opacity-40" /><p className="font-semibold">No attendance yet</p>
          <p className="text-xs mt-1">Use Clock In above to start.</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-50">
          {days.map((d) => (
            <div key={d.label} className="flex items-center gap-3 px-5 py-3.5">
              <CalendarDays size={16} className="text-slate-300 shrink-0" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-slate-800">{d.label}</p>
                <p className="text-xs text-slate-400">
                  {d.firstIn ? `In ${hhmm(d.firstIn)}` : "—"}{d.lastOut ? ` · Out ${hhmm(d.lastOut)}` : ""}
                </p>
              </div>
              {hours(d.firstIn, d.lastOut) && <span className="text-sm font-bold text-slate-700 shrink-0">{hours(d.firstIn, d.lastOut)}h</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
