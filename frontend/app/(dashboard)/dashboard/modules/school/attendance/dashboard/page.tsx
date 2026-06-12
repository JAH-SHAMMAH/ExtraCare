"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock, UserX, BarChart3, LogIn } from "lucide-react";
import { schoolApi } from "@/lib/api";
import { useDailyAttendance, useMonthlyAttendance } from "@/hooks/useAttendance";
import { cn } from "@/lib/utils";
import {
  DailySummaryCards,
  StatusBadge,
  StatCard,
  formatClock,
  MONTH_NAMES,
} from "@/components/attendance/shared";

const today = () => new Date().toISOString().split("T")[0];

interface ClassOption { id: string; name: string; level?: string | null }

/**
 * Admin Attendance Dashboard.
 * School-wide daily breakdown with late-arrival and absence analytics, a class
 * filter, the full roster, and a month-to-date summary. Read-only insights —
 * roll-call marking lives on the existing Attendance Tracker page.
 */
export default function AdminAttendanceDashboardPage() {
  const [date, setDate] = useState(today());
  const [classId, setClassId] = useState("");

  const { data: classesRaw } = useQuery({
    queryKey: ["school", "classes", "for-attendance"],
    queryFn: () => schoolApi.classes.list({ page_size: 200 }),
    staleTime: 5 * 60_000,
  });
  const classes: ClassOption[] = useMemo(() => {
    const list = (classesRaw as any)?.items ?? (Array.isArray(classesRaw) ? classesRaw : []);
    return list as ClassOption[];
  }, [classesRaw]);

  const { data: summary, isLoading } = useDailyAttendance(date, classId || undefined);

  const now = new Date();
  const { data: monthly } = useMonthlyAttendance(now.getFullYear(), now.getMonth() + 1);

  const rows = summary?.rows ?? [];
  const lateArrivals = rows.filter((r) => r.status === "late");
  const absentees = rows.filter((r) => !r.status || r.status === "absent");

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span><span>/</span>
          <Link href="/dashboard/modules/school/attendance" className="hover:text-brand-600 flex items-center gap-1">
            <ArrowLeft size={12} /> Attendance
          </Link>
          <span>/</span>
          <span className="text-brand-600 font-semibold">Insights</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Attendance Insights</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          School-wide daily attendance, late arrivals, and absences.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="label">Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input" />
        </div>
        <div>
          <label className="label">Class</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className="input min-w-[14rem]">
            <option value="">All classes</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.level ? ` · ${c.level}` : ""}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Daily summary */}
      <div className="mb-6">
        <DailySummaryCards
          present={summary?.present ?? 0}
          late={summary?.late ?? 0}
          absent={summary?.absent ?? 0}
          excused={summary?.excused ?? 0}
          total={summary?.total_students ?? 0}
        />
      </div>

      {/* Late + absence analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <AnalyticsList
          title="Late arrivals"
          icon={Clock}
          tone="text-amber-600"
          empty="No late arrivals today."
          loading={isLoading}
          rows={lateArrivals.map((r) => ({ id: r.student_id, name: r.student_name, meta: `Arrived ${formatClock(r.first_check_in)}` }))}
        />
        <AnalyticsList
          title="Absent / not checked in"
          icon={UserX}
          tone="text-rose-600"
          empty="Everyone is accounted for."
          loading={isLoading}
          rows={absentees.map((r) => ({ id: r.student_id, name: r.student_name, meta: "No check-in recorded" }))}
        />
      </div>

      {/* Month-to-date + full roster */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3 flex items-center gap-1.5">
            <BarChart3 size={13} /> {MONTH_NAMES[now.getMonth()]} {now.getFullYear()} (school-wide)
          </p>
          <div className="grid grid-cols-2 gap-4">
            <StatCard label="Present" value={monthly?.present ?? 0} accent="text-emerald-600" />
            <StatCard label="Late" value={monthly?.late ?? 0} accent="text-amber-600" />
            <StatCard label="Absent" value={monthly?.absent ?? 0} accent="text-rose-600" />
            <StatCard label="Days logged" value={monthly?.days_recorded ?? 0} />
          </div>
        </div>

        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-slate-100">
            <h2 className="text-sm font-black text-slate-900">Roster · {new Date(date).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</h2>
          </div>
          <div className="max-h-[30rem] overflow-y-auto">
            <table className="w-full text-left">
              <thead className="sticky top-0">
                <tr className="bg-slate-50 border-b border-slate-100">
                  {["Student", "Status", "Check-in", "Check-out"].map((h) => (
                    <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}><td colSpan={4} className="px-5 py-4"><div className="h-4 w-40 bg-slate-100 rounded animate-pulse" /></td></tr>
                  ))
                ) : rows.length === 0 ? (
                  <tr><td colSpan={4} className="px-5 py-12 text-center text-sm text-slate-400">No students found for this selection.</td></tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.student_id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-5 py-3 text-sm font-semibold text-slate-900">{r.student_name}</td>
                      <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{formatClock(r.first_check_in)}</td>
                      <td className="px-5 py-3 text-sm text-slate-600 tabular-nums">{formatClock(r.last_check_out)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function AnalyticsList({
  title, icon: Icon, tone, empty, loading, rows,
}: {
  title: string;
  icon: typeof Clock;
  tone: string;
  empty: string;
  loading: boolean;
  rows: { id: string; name: string; meta: string }[];
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between">
        <h2 className="text-sm font-black text-slate-900 flex items-center gap-2">
          <Icon size={15} className={tone} /> {title}
        </h2>
        <span className="badge bg-slate-50 text-slate-600 border-slate-200">{rows.length}</span>
      </div>
      <div className="divide-y divide-slate-50 max-h-72 overflow-y-auto">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="px-5 py-3"><div className="h-4 w-44 bg-slate-100 rounded animate-pulse" /></div>
          ))
        ) : rows.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-400">{empty}</div>
        ) : (
          rows.map((r) => (
            <div key={r.id} className="px-5 py-3 flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-800">{r.name}</span>
              <span className="text-xs text-slate-400">{r.meta}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
