"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, LogIn, LogOut, AlertCircle, CalendarDays } from "lucide-react";
import { useMyContexts } from "@/hooks/useMyContexts";
import {
  useMonthlyAttendance,
  useStudentAttendanceHistory,
} from "@/hooks/useAttendance";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { TableSkeleton } from "@/components/loading/Skeleton";
import { cn, getInitials } from "@/lib/utils";
import {
  AttendanceAlertsPanel,
  StatCard,
  formatClock,
  MONTH_NAMES,
} from "@/components/attendance/shared";

/**
 * Parent Attendance Dashboard.
 * Per-child monthly summary + recent check-in/out history, alongside the live
 * arrival/departure notification feed. Data is guardian-scoped server-side —
 * parents only ever see their own children.
 */
export default function ParentAttendancePage() {
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const children = data?.as_parent?.children ?? [];

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = useMemo(
    () => children.find((c) => c.id === selectedId) ?? children[0] ?? null,
    [children, selectedId],
  );

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  const { data: monthly } = useMonthlyAttendance(year, month, selected?.id, !!selected);
  const { data: history = [], isLoading: histLoading } = useStudentAttendanceHistory(selected?.id);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <Link href="/dashboard/my-children" className="hover:text-brand-600 flex items-center gap-1">
            <ArrowLeft size={12} /> Parent portal
          </Link>
          <span>/</span>
          <span className="text-brand-600 font-semibold">Attendance</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Attendance</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Arrival and departure activity for your children, with instant alerts.
        </p>
      </div>

      {showSkeleton ? (
        <TableSkeleton rows={4} cols={4} />
      ) : children.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          {/* Child selector */}
          {children.length > 1 && (
            <div className="flex flex-wrap gap-2 mb-6">
              {children.map((c) => {
                const active = selected?.id === c.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => setSelectedId(c.id)}
                    className={cn(
                      "flex items-center gap-2 pl-1.5 pr-3 py-1.5 rounded-full border text-sm font-semibold transition-all",
                      active
                        ? "bg-brand-600 text-white border-brand-600"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50",
                    )}
                  >
                    <span className={cn(
                      "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-black",
                      active ? "bg-white/20 text-white" : "bg-brand-50 text-brand-700",
                    )}>
                      {getInitials(`${c.first_name} ${c.last_name}`)}
                    </span>
                    {c.first_name}
                  </button>
                );
              })}
            </div>
          )}

          {selected && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: monthly summary + history */}
              <div className="lg:col-span-2 space-y-6">
                <div>
                  <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">
                    {MONTH_NAMES[month - 1]} {year} · {selected.first_name} {selected.last_name}
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <StatCard label="Present" value={monthly?.present ?? 0} accent="text-emerald-600" />
                    <StatCard label="Late" value={monthly?.late ?? 0} accent="text-amber-600" />
                    <StatCard label="Absent" value={monthly?.absent ?? 0} accent="text-rose-600" />
                    <StatCard label="Excused" value={monthly?.excused ?? 0} accent="text-blue-600" />
                    <StatCard label="Days logged" value={monthly?.days_recorded ?? 0} />
                  </div>
                </div>

                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-5 py-3.5 border-b border-slate-100 flex items-center gap-2">
                    <CalendarDays size={15} className="text-brand-600" />
                    <h2 className="text-sm font-black text-slate-900">Recent check-ins & check-outs</h2>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr className="bg-slate-50/80 border-b border-slate-100">
                          {["Activity", "Date", "Time"].map((h) => (
                            <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {histLoading ? (
                          Array.from({ length: 5 }).map((_, i) => (
                            <tr key={i}><td colSpan={3} className="px-5 py-4"><div className="h-4 w-40 bg-slate-100 rounded animate-pulse" /></td></tr>
                          ))
                        ) : history.length === 0 ? (
                          <tr><td colSpan={3} className="px-5 py-12 text-center text-sm text-slate-400">No attendance activity recorded yet.</td></tr>
                        ) : (
                          history.map((e) => {
                            const isOut = e.event_type === "check_out";
                            const Icon = isOut ? LogOut : LogIn;
                            const d = new Date(e.event_time);
                            return (
                              <tr key={e.id} className="hover:bg-slate-50/70 transition-colors">
                                <td className="px-5 py-3.5">
                                  <span className={cn(
                                    "inline-flex items-center gap-1.5 text-sm font-semibold",
                                    isOut ? "text-slate-600" : "text-emerald-700",
                                  )}>
                                    <Icon size={14} />
                                    {isOut ? "Checked out" : "Checked in"}
                                  </span>
                                </td>
                                <td className="px-5 py-3.5 text-sm text-slate-600">
                                  {d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}
                                </td>
                                <td className="px-5 py-3.5 text-sm font-medium text-slate-900 tabular-nums">{formatClock(e.event_time)}</td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Right: live alerts */}
              <div className="lg:col-span-1">
                <AttendanceAlertsPanel />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
      <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mx-auto mb-4">
        <AlertCircle size={26} className="text-amber-500" />
      </div>
      <h2 className="text-base font-bold text-slate-800 mb-1">No children linked</h2>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        A school administrator needs to link your account to your child&apos;s student record before you can follow their attendance.
      </p>
    </div>
  );
}
