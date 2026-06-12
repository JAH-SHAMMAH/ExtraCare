"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  GraduationCap, Clock, BookOpen, Users as UsersIcon, CheckSquare, ArrowRight,
  ClipboardList, Award, Calendar, NotebookPen,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import {
  PageHeaderSkeleton, CardGridSkeleton, Skeleton,
} from "@/components/loading/Skeleton";
import { cn } from "@/lib/utils";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function TeacherHome() {
  const { user, org } = useAuthStore();
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const [timeOfDay, setTimeOfDay] = useState("");

  useEffect(() => {
    setTimeOfDay(getTimeOfDay());
  }, []);

  if (showSkeleton) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <PageHeaderSkeleton />
        <CardGridSkeleton />
      </div>
    );
  }

  const teacher = data?.as_teacher;
  const today = teacher?.today_slots ?? [];
  const stats = teacher?.stats;
  const classes = teacher?.classes ?? [];
  const subjects = teacher?.subjects ?? [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          {timeOfDay ? `Good ${timeOfDay}` : "Welcome"}, {user?.full_name?.split(" ")[0]} 👋
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          {org?.name} · Teaching at a glance
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={BookOpen}
          iconClass="bg-emerald-50 text-emerald-600"
          label="My Classes"
          value={stats?.classes_count ?? 0}
        />
        <StatCard
          icon={GraduationCap}
          iconClass="bg-indigo-50 text-indigo-600"
          label="My Subjects"
          value={stats?.subjects_count ?? 0}
        />
        <StatCard
          icon={Clock}
          iconClass="bg-sky-50 text-sky-600"
          label="Today's Lessons"
          value={stats?.today_lessons ?? 0}
        />
        <StatCard
          icon={CheckSquare}
          iconClass="bg-amber-50 text-amber-600"
          label="Pending Grades"
          value={stats?.pending_grades ?? 0}
          highlight={!!stats?.pending_grades}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        {/* Today's schedule */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Today's Schedule</h3>
              <p className="text-xs text-slate-400 mt-0.5">{DAYS[new Date().getDay() === 0 ? 6 : new Date().getDay() - 1]} · {today.length} lesson{today.length === 1 ? "" : "s"}</p>
            </div>
            <Link href="/dashboard/modules/school/timetable" className="text-xs text-brand-600 font-semibold hover:underline flex items-center gap-1">
              Full timetable <ArrowRight size={12} />
            </Link>
          </div>
          <div className="divide-y divide-slate-50">
            {today.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-slate-400">
                No lessons scheduled for today.
              </div>
            ) : (
              today.map((slot) => (
                <div key={slot.id} className="px-5 py-3.5 flex items-center gap-4 hover:bg-slate-50 transition-colors">
                  <div className="text-xs font-bold text-slate-500 tabular-nums w-20">
                    {slot.start_time}–{slot.end_time}
                  </div>
                  <div className="w-1 h-10 rounded bg-brand-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{slot.subject_name ?? "Lesson"}</p>
                    <p className="text-xs text-slate-500 truncate">
                      {slot.room ? `Room ${slot.room}` : "—"}
                    </p>
                  </div>
                  <Link
                    href="/dashboard/modules/school/cbt/live"
                    className="text-xs font-semibold text-brand-600 hover:underline"
                  >
                    Go live
                  </Link>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick actions */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-2">
          <h3 className="text-sm font-bold text-slate-800 mb-3">Quick Actions</h3>
          <QuickLink href="/dashboard/modules/school/lessons" icon={NotebookPen} label="Plan lessons" />
          <QuickLink href="/dashboard/modules/school/attendance" icon={ClipboardList} label="Mark attendance" />
          <QuickLink href="/dashboard/modules/school/grades" icon={Award} label="Grade submissions" />
          <QuickLink href="/dashboard/modules/school/eclassroom" icon={BookOpen} label="Assign homework" />
          <QuickLink href="/dashboard/modules/school/timetable" icon={Calendar} label="View timetable" />
        </div>
      </div>

      {/* Classes + Subjects */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        <ListCard
          title="Classes I teach"
          empty="You are not assigned to any classes yet."
          items={classes.map((c) => ({
            key: c.id,
            primary: c.name,
            secondary: [c.level, c.academic_year].filter(Boolean).join(" · ") || null,
            href: `/dashboard/modules/school/classes`,
          }))}
          icon={UsersIcon}
        />
        <ListCard
          title="Subjects I teach"
          empty="No subjects assigned to you."
          items={subjects.map((s) => ({
            key: s.id,
            primary: s.name,
            secondary: s.code,
            href: `/dashboard/modules/school/subjects`,
          }))}
          icon={GraduationCap}
        />
      </div>
    </div>
  );
}

// ── Shared bits ──────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon,
  iconClass,
  label,
  value,
  highlight = false,
}: {
  icon: typeof Clock;
  iconClass: string;
  label: string;
  value: number | string;
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      "bg-white rounded-xl border p-5 shadow-sm",
      highlight ? "border-amber-300 bg-amber-50/40" : "border-slate-200/70",
    )}>
      <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center mb-4", iconClass)}>
        <Icon size={16} />
      </div>
      <div className="text-2xl font-black tracking-tight text-slate-900">{value}</div>
      <p className="text-xs font-bold uppercase tracking-widest text-slate-500 mt-1">{label}</p>
    </div>
  );
}

function QuickLink({
  href, icon: Icon, label,
}: {
  href: string;
  icon: typeof Clock;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 text-sm font-medium transition-all group"
    >
      <Icon size={15} className="group-hover:text-brand-600" />
      {label}
    </Link>
  );
}

function ListCard({
  title, empty, items, icon: Icon,
}: {
  title: string;
  empty: string;
  items: Array<{ key: string; primary: string; secondary: string | null; href: string }>;
  icon: typeof Clock;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100">
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      </div>
      <div className="divide-y divide-slate-50">
        {items.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-slate-400">{empty}</div>
        ) : (
          items.map((it) => (
            <Link
              key={it.key}
              href={it.href}
              className="flex items-center gap-3 px-5 py-3.5 hover:bg-slate-50 transition-colors"
            >
              <div className="w-9 h-9 rounded-lg bg-brand-50 text-brand-700 flex items-center justify-center shrink-0">
                <Icon size={15} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-900 truncate">{it.primary}</p>
                {it.secondary && <p className="text-xs text-slate-500 truncate">{it.secondary}</p>}
              </div>
              <ArrowRight size={14} className="text-slate-300" />
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}

// Re-export Skeleton so this file stays self-contained for imports.
export { Skeleton };
