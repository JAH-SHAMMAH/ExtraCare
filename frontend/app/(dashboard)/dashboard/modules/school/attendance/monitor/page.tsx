"use client";

import { useEffect, useRef, useState } from "react";
import {
  useAttendanceMonitor, useRecordAttendanceEvent, useStudents,
  type AttendanceMonitorCard,
} from "@/hooks/useSchool";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import {
  Loader2, LogIn, LogOut, Users2, Clock, Radio, TrendingUp,
  Volume2, VolumeX, Search, UserPlus,
} from "lucide-react";

/**
 * School Live Attendance Monitor (Educare parity). Live campus presence over the
 * check-in/out event backbone. Two staff conveniences layered on top:
 *   • manual check-in / check-out — a fallback when no ZKTeco device is present;
 *   • a spoken announcement when a parent arrives (a check-out) — a browser
 *     text-to-speech stand-in for the PA system, opt-in via the speaker toggle.
 */
export default function AttendanceMonitorPage() {
  const { data, isLoading } = useAttendanceMonitor();
  const canWrite = useHasPermission("school:attendance:write");
  const [tab, setTab] = useState<"live" | "arrivals">("live");
  const [announce, setAnnounce] = useState(false);

  // Announce NEW departures only. Seed the "seen" set on first load so the
  // existing backlog is never replayed; thereafter a fresh check-out speaks.
  const seen = useRef<Set<string>>(new Set());
  const inited = useRef(false);
  useEffect(() => {
    if (!data) return;
    const outs = (data.recent || []).filter((r) => r.type === "check_out");
    if (!inited.current) {
      outs.forEach((r) => seen.current.add(r.student_id));
      inited.current = true;
      return;
    }
    for (const r of outs) {
      if (!seen.current.has(r.student_id)) {
        seen.current.add(r.student_id);
        if (announce) speak(`Attention. Parent of ${r.student_name}${r.class_name ? `, ${r.class_name}` : ""}, has arrived for pick-up.`);
      }
    }
  }, [data, announce]);

  const toggleAnnounce = () => {
    const next = !announce;
    setAnnounce(next);
    if (next) speak("Audio announcements enabled.");   // doubles as the user gesture that unlocks audio
    else if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="rounded-2xl bg-slate-900 text-white px-6 py-5 mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="text-amber-400 font-black tabular-nums text-lg">{data?.date ?? "—"}</p>
          <h1 className="text-xl font-black tracking-tight">School Live Attendance Monitor</h1>
          <p className="text-slate-300 text-sm mt-0.5">Live overview of campus presence — who remains on-site and who has departed.</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={toggleAnnounce} title="Speak an announcement when a parent arrives" className={cn("inline-flex items-center gap-1.5 text-xs font-bold rounded-lg px-2.5 py-1.5", announce ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-slate-300 hover:bg-white/20")}>
            {announce ? <Volume2 size={13} /> : <VolumeX size={13} />} Announce
          </button>
          <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-400"><Radio size={13} /> Live</span>
        </div>
      </div>

      {announce && <p className="text-[11px] text-slate-400 -mt-3 mb-4">🔊 This page uses your system audio to announce parent arrivals. Connect to a PA system for best results.</p>}

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

      {canWrite && <ManualRecorder />}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 p-1 inline-flex mb-4">
        {[{ id: "live" as const, label: "Live Overview" }, { id: "arrivals" as const, label: "Parent Arrivals Log" }].map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cn("px-4 py-1.5 text-xs font-bold rounded-lg transition-colors", tab === t.id ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100")}>{t.label}</button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-16 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>
      ) : tab === "live" ? (
        <StudentsInSchool cards={data?.students_in_school ?? []} canWrite={canWrite} />
      ) : (
        <ArrivalsLog recent={data?.recent ?? []} />
      )}
    </div>
  );
}

function speak(text: string) {
  try {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch { /* audio best-effort */ }
}

function Stat({ icon: Icon, label, value, tint }: { icon: any; label: string; value?: number; tint: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-center gap-4">
      <div className={cn("w-11 h-11 rounded-lg bg-slate-50 flex items-center justify-center", tint)}><Icon size={18} /></div>
      <div><p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">{label}</p><p className={cn("text-3xl font-black tabular-nums", tint)}>{value ?? 0}</p></div>
    </div>
  );
}

// ── Manual check-in / check-out (ZKTeco fallback) ─────────────────────────────

function ManualRecorder() {
  const [search, setSearch] = useState("");
  const { data: students } = useStudents({ search: search || undefined, page_size: 8 });
  const record = useRecordAttendanceEvent();
  const items = (students?.items ?? []) as Array<{ id: string; first_name: string; last_name: string; student_id: string }>;

  const doRecord = (student_id: string, event_type: "check_in" | "check_out") =>
    record.mutate({ student_id, event_type }, { onSuccess: () => setSearch("") });

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5">
      <div className="flex items-center gap-2 mb-3"><UserPlus size={15} className="text-brand-600" /><h2 className="text-sm font-bold text-slate-800">Manual check-in / check-out</h2><span className="text-[11px] text-slate-400">— fallback when no device is connected</span></div>
      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search a student by name or ID…" className="input pl-9" />
      </div>
      {search && (
        <div className="mt-2 rounded-lg border border-slate-200 divide-y divide-slate-50 max-w-2xl">
          {items.length === 0 ? <p className="px-3 py-2 text-xs text-slate-400">No students match.</p> : items.map((s) => (
            <div key={s.id} className="flex items-center gap-2 px-3 py-2">
              <span className="flex-1 text-sm text-slate-700"><span className="font-semibold">{s.first_name} {s.last_name}</span><span className="text-slate-400 ml-2 text-xs">{s.student_id}</span></span>
              <button onClick={() => doRecord(s.id, "check_in")} disabled={record.isPending} className="btn-secondary text-xs py-1 gap-1"><LogIn size={12} /> Check in</button>
              <button onClick={() => doRecord(s.id, "check_out")} disabled={record.isPending} className="btn-secondary text-xs py-1 gap-1"><LogOut size={12} /> Check out</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StudentsInSchool({ cards, canWrite }: { cards: AttendanceMonitorCard[]; canWrite: boolean }) {
  const record = useRecordAttendanceEvent();
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
              <div className="flex items-center justify-between mt-2">
                {c.check_in ? <span className="text-[11px] text-emerald-600">In {c.check_in}</span> : <span />}
                {canWrite && (
                  <button onClick={() => record.mutate({ student_id: c.student_id, event_type: "check_out" })} disabled={record.isPending} className="btn-secondary text-[11px] py-1 gap-1"><LogOut size={11} /> Check out</button>
                )}
              </div>
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
