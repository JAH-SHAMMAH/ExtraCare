"use client";

import { useEffect, useMemo, useState } from "react";
import { useSessions } from "@/hooks/usePlatform";
import { useClasses, useSubjects } from "@/hooks/useSchool";
import { useStaff } from "@/hooks/useUsers";
import { usePeriodGroups, usePeriods, useSchedules, useUpsertSchedule, useDeleteSchedule } from "@/hooks/useTimetableModule";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { cn } from "@/lib/utils";
import { CalendarRange, Loader2, X, Trash2, Plus } from "lucide-react";
import type { PeriodGroup, Period, PeriodSchedule } from "@/types";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function ManageSchedulesPage() {
  const canWrite = useHasPermission("school:timetable:write");
  const { data: pgData } = usePeriodGroups();
  const { data: sessions } = useSessions();
  const { data: classesData } = useClasses({ page_size: 200 });
  const sessionNames = useMemo(() => Array.from(new Set((sessions ?? []).map((s: any) => s.name))), [sessions]);

  const [session, setSession] = useState("");
  const [groupId, setGroupId] = useState("");
  const [day, setDay] = useState(0);
  const groups: PeriodGroup[] = pgData?.items ?? [];
  const classes = classesData?.items ?? [];

  useEffect(() => { if (!session && sessionNames.length) setSession(sessionNames[0]); }, [sessionNames, session]);
  useEffect(() => { if (!groupId && groups.length) setGroupId(groups[0].id); }, [groups, groupId]);

  const { data: periodsData, isLoading } = usePeriods({ period_group_id: groupId || null, academic_year: session || undefined });
  const { data: schedData } = useSchedules({ period_group_id: groupId || null, academic_year: session || undefined });
  const del = useDeleteSchedule();
  const periods: Period[] = (periodsData?.items ?? []).filter((p) => p.day_of_week === day);
  const schedules: PeriodSchedule[] = schedData?.items ?? [];
  const cellFor = (periodId: string, classId: string) => schedules.find((s) => s.period_id === periodId && s.class_id === classId);

  const [assign, setAssign] = useState<{ period: Period; classId: string; className: string } | null>(null);

  return (
    <div className="p-8 max-w-full mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>TimeTable</span><span>/</span><span className="text-brand-600 font-semibold">Manage Schedules</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Manage Schedules</h1>
        <p className="text-slate-500 text-sm mt-0.5">Place subjects and teachers into each period, per class. Non-lesson periods appear as bands.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 mb-5 flex flex-wrap gap-4 items-end">
        <div><label className="label">Period Group</label><select value={groupId} onChange={(e) => setGroupId(e.target.value)} className="input min-w-[180px]"><option value="">Select…</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
        <div><label className="label">Session</label><select value={session} onChange={(e) => setSession(e.target.value)} className="input min-w-[150px]"><option value="">All</option>{sessionNames.map((n) => <option key={n} value={n}>{n}</option>)}</select></div>
        <div><label className="label">Day</label><select value={day} onChange={(e) => setDay(Number(e.target.value))} className="input min-w-[150px]">{DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select></div>
      </div>

      {!groupId ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><CalendarRange size={32} className="mx-auto mb-3 opacity-40" /><p className="font-semibold">Select a period group</p></div>
      ) : isLoading ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></div>
      ) : periods.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><p className="font-semibold">No periods for {DAYS[day]}</p><p className="text-xs mt-1">Generate periods in Manage Periods first.</p></div>
      ) : classes.length === 0 ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center text-slate-400"><p className="font-semibold">No classes yet</p></div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <table className="text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-100">
                <th className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 sticky left-0 bg-slate-50 z-10 min-w-[130px]">Period</th>
                {classes.map((c: any) => <th key={c.id} className="px-4 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500 whitespace-nowrap min-w-[150px]">{c.name}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {periods.map((p) => {
                const isLesson = p.period_type === "LESSON";
                return (
                  <tr key={p.id} className="hover:bg-slate-50/40">
                    <td className="px-4 py-2 text-xs font-semibold text-slate-600 sticky left-0 bg-white z-10 whitespace-nowrap">{p.start_time}–{p.end_time}<span className="block text-[10px] font-normal text-slate-400">{p.period_type}</span></td>
                    {!isLesson ? (
                      <td colSpan={classes.length} className="px-4 py-2 text-center text-xs font-bold uppercase tracking-wide text-amber-700 bg-amber-50">{p.period_type}</td>
                    ) : classes.map((c: any) => {
                      const s = cellFor(p.id, c.id);
                      return (
                        <td key={c.id} className="px-2 py-2 align-top min-w-[150px]">
                          {s ? (
                            <div className="rounded-lg bg-brand-50 border border-brand-100 px-2 py-1.5 text-xs">
                              <p className="font-bold text-brand-700 truncate">{s.subject_name}</p>
                              {s.teacher_name && <p className="text-slate-500 truncate">{s.teacher_name}</p>}
                              {canWrite && <button onClick={() => { if (confirm("Remove?")) del.mutate(s.id); }} className="text-rose-400 hover:text-rose-600 mt-0.5"><Trash2 size={11} /></button>}
                            </div>
                          ) : canWrite ? (
                            <button onClick={() => setAssign({ period: p, classId: c.id, className: c.name })} className="w-full rounded-lg border border-dashed border-slate-200 text-slate-300 hover:text-brand-500 hover:border-brand-300 py-1.5 flex items-center justify-center"><Plus size={14} /></button>
                          ) : <span className="text-slate-200">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {assign && <AssignModal ctx={assign} session={session} onClose={() => setAssign(null)} />}
    </div>
  );
}

function AssignModal({ ctx, session, onClose }: { ctx: { period: Period; classId: string; className: string }; session: string; onClose: () => void }) {
  const { data: subjectsData } = useSubjects({ page_size: 200 });
  const { data: staffData } = useStaff();
  const upsert = useUpsertSchedule();

  const subjects = subjectsData?.items ?? [];
  const staff = ((staffData as any)?.items ?? staffData ?? []) as any[];
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");

  const submit = () => upsert.mutate({ period_id: ctx.period.id, class_id: ctx.classId, subject_id: subjectId, teacher_id: teacherId || null, academic_year: session || null }, { onSuccess: onClose });

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100"><div><h3 className="text-sm font-bold text-slate-800">Assign schedule</h3><p className="text-xs text-slate-400">{ctx.className} · {ctx.period.start_time}–{ctx.period.end_time}</p></div><button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X size={16} /></button></div>
        <div className="px-6 py-4 space-y-4">
          <div><label className="label">Subject *</label><select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className="input"><option value="">Select…</option>{subjects.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          <div><label className="label">Teacher</label><select value={teacherId} onChange={(e) => setTeacherId(e.target.value)} className="input"><option value="">—</option>{staff.map((u: any) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</select></div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100"><button onClick={onClose} className="btn-secondary">Cancel</button><button onClick={submit} disabled={!subjectId || upsert.isPending} className="btn-primary gap-2">{upsert.isPending && <Loader2 size={15} className="animate-spin" />}Save</button></div>
      </div>
    </div>
  );
}
