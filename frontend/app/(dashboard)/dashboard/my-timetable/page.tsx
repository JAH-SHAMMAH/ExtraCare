"use client";

import { Calendar } from "lucide-react";
import { useMyContexts, type ContextSlot } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { PageHeaderSkeleton, Skeleton } from "@/components/loading/Skeleton";
import { cn } from "@/lib/utils";

const DAYS = [
  { idx: 0, label: "Monday", short: "Mon" },
  { idx: 1, label: "Tuesday", short: "Tue" },
  { idx: 2, label: "Wednesday", short: "Wed" },
  { idx: 3, label: "Thursday", short: "Thu" },
  { idx: 4, label: "Friday", short: "Fri" },
];

/**
 * Student timetable — weekly view derived from `/me/contexts` so there's no
 * extra fetch. Groups slots by weekday; within a day, orders by start_time.
 * Today's column is highlighted.
 */
export default function MyTimetablePage() {
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const slots = data?.as_student?.timetable ?? [];
  const className = data?.as_student?.class?.name ?? null;

  const todayIdx = (new Date().getDay() + 6) % 7; // JS: Sun=0; we want Mon=0.

  const byDay: Record<number, ContextSlot[]> = {};
  for (const s of slots) {
    if (!byDay[s.day_of_week]) byDay[s.day_of_week] = [];
    byDay[s.day_of_week].push(s);
  }
  for (const d of Object.keys(byDay)) {
    byDay[Number(d)].sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""));
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Student</span><span>/</span>
          <span className="text-brand-600 font-semibold">My Timetable</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Timetable</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Weekly schedule{className ? ` for ${className}` : ""}.
        </p>
      </div>

      {showSkeleton ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => (
            <div key={d.idx} className="bg-white rounded-xl border border-slate-200 p-4 space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-14 w-full rounded-lg" />
              <Skeleton className="h-14 w-full rounded-lg" />
            </div>
          ))}
        </div>
      ) : slots.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {DAYS.map((d) => (
            <DayColumn
              key={d.idx}
              label={d.label}
              short={d.short}
              slots={byDay[d.idx] || []}
              isToday={d.idx === todayIdx}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DayColumn({
  label, short, slots, isToday,
}: {
  label: string;
  short: string;
  slots: ContextSlot[];
  isToday: boolean;
}) {
  return (
    <div className={cn(
      "bg-white rounded-xl border overflow-hidden",
      isToday ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200",
    )}>
      <div className={cn(
        "px-4 py-3 border-b flex items-center justify-between",
        isToday ? "bg-brand-50 border-brand-100" : "bg-slate-50/50 border-slate-100",
      )}>
        <div>
          <p className={cn("text-xs font-black uppercase tracking-widest", isToday ? "text-brand-700" : "text-slate-500")}>
            {short}
          </p>
          <p className={cn("text-[10px]", isToday ? "text-brand-600" : "text-slate-400")}>
            {label}
          </p>
        </div>
        {isToday && <span className="text-[10px] font-bold uppercase tracking-wider text-brand-600">Today</span>}
      </div>
      <div className="p-2 space-y-2 min-h-[240px]">
        {slots.length === 0 ? (
          <p className="text-xs text-slate-300 text-center py-6">No lessons</p>
        ) : (
          slots.map((s) => (
            <div
              key={s.id}
              className={cn(
                "rounded-lg p-3 border",
                isToday ? "bg-brand-50/50 border-brand-200" : "bg-slate-50 border-slate-100",
              )}
            >
              <p className="text-[10px] font-bold tabular-nums text-slate-500">
                {s.start_time}–{s.end_time}
              </p>
              <p className="text-sm font-bold text-slate-900 mt-0.5 truncate">
                {s.subject_name ?? "Lesson"}
              </p>
              {s.room && <p className="text-[10px] text-slate-500 mt-0.5">Room {s.room}</p>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
      <div className="w-14 h-14 rounded-2xl bg-slate-100 flex items-center justify-center mx-auto mb-4">
        <Calendar size={26} className="text-slate-400" />
      </div>
      <h2 className="text-base font-bold text-slate-800 mb-1">No timetable yet</h2>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        Your class timetable hasn&apos;t been set up yet. Check back after an admin schedules your lessons.
      </p>
    </div>
  );
}
