"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, LogIn, LogOut, ClipboardList, Loader2 } from "lucide-react";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDailyAttendance, useRecordManualAttendance } from "@/hooks/useAttendance";
import { cn } from "@/lib/utils";
import {
  DailySummaryCards,
  StatusBadge,
  formatClock,
} from "@/components/attendance/shared";

const today = () => new Date().toISOString().split("T")[0];

/**
 * Teacher Attendance Dashboard.
 * Pick one of the classes you teach, see who's in for the day, and record a
 * manual check-in/out (which notifies the child's parents instantly).
 */
export default function TeacherAttendancePage() {
  const { data: contexts } = useMyContexts();
  const classes = contexts?.as_teacher?.classes ?? [];

  const [classId, setClassId] = useState("");
  const [date, setDate] = useState(today());

  // Default to the first class once contexts resolve.
  useEffect(() => {
    if (!classId && classes.length > 0) setClassId(classes[0].id);
  }, [classes, classId]);

  const { data: summary, isLoading } = useDailyAttendance(date, classId, !!classId);
  const recordManual = useRecordManualAttendance();
  const rows = summary?.rows ?? [];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <Link href="/dashboard/my-classes" className="hover:text-brand-600 flex items-center gap-1">
            <ArrowLeft size={12} /> My Classes
          </Link>
          <span>/</span>
          <span className="text-brand-600 font-semibold">Attendance</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Class Attendance</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Daily attendance for your classes. Recording a check-in alerts parents immediately.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-6 flex flex-wrap items-end gap-4">
        <div>
          <label className="label">Class</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)} className="input min-w-[14rem]">
            {classes.length === 0 && <option value="">No classes assigned</option>}
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}{c.level ? ` · ${c.level}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input" />
        </div>
      </div>

      {!classId ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400 text-sm">
          <ClipboardList size={32} className="mx-auto mb-2 opacity-50" />
          You don&apos;t have any classes assigned yet.
        </div>
      ) : (
        <>
          <div className="mb-6">
            <DailySummaryCards
              present={summary?.present ?? 0}
              late={summary?.late ?? 0}
              absent={summary?.absent ?? 0}
              excused={summary?.excused ?? 0}
              total={summary?.total_students ?? 0}
            />
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-50/80 border-b border-slate-100">
                  {["Student", "Status", "Check-in", "Check-out", "Record"].map((h) => (
                    <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {isLoading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}><td colSpan={5} className="px-5 py-4"><div className="h-4 w-48 bg-slate-100 rounded animate-pulse" /></td></tr>
                  ))
                ) : rows.length === 0 ? (
                  <tr><td colSpan={5} className="px-5 py-16 text-center text-slate-400 text-sm">No students in this class.</td></tr>
                ) : (
                  rows.map((r) => {
                    const busy = recordManual.isPending && recordManual.variables?.student_id === r.student_id;
                    return (
                      <tr key={r.student_id} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-5 py-3.5 text-sm font-bold text-slate-900">{r.student_name}</td>
                        <td className="px-5 py-3.5"><StatusBadge status={r.status} /></td>
                        <td className="px-5 py-3.5 text-sm text-slate-600 tabular-nums">{formatClock(r.first_check_in)}</td>
                        <td className="px-5 py-3.5 text-sm text-slate-600 tabular-nums">{formatClock(r.last_check_out)}</td>
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => recordManual.mutate({ student_id: r.student_id, event_type: "check_in" })}
                              disabled={recordManual.isPending}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-emerald-200 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50 transition-all"
                            >
                              {busy ? <Loader2 size={12} className="animate-spin" /> : <LogIn size={12} />} In
                            </button>
                            <button
                              onClick={() => recordManual.mutate({ student_id: r.student_id, event_type: "check_out" })}
                              disabled={recordManual.isPending}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-all"
                            >
                              <LogOut size={12} /> Out
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
