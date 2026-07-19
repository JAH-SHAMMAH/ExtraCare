"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Clock, BookOpen, Calendar, CheckSquare, ArrowRight, GraduationCap,
  FileText, MonitorCheck, Library, Newspaper,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { useMyContexts, type ContextSlot } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { PageHeaderSkeleton, CardGridSkeleton } from "@/components/loading/Skeleton";
import { NewsFeed } from "@/components/feed/NewsFeed";
import { cn, getInitials } from "@/lib/utils";

const DAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function StudentHome() {
  const { user } = useAuthStore();
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const [timeOfDay, setTimeOfDay] = useState("");

  useEffect(() => {
    setTimeOfDay(getTimeOfDay());
  }, []);

  if (showSkeleton) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <PageHeaderSkeleton />
        <CardGridSkeleton count={3} />
      </div>
    );
  }

  const student = data?.as_student;
  const today = student?.today_slots ?? [];
  const stats = student?.stats;
  const nextSlot = getNextSlot(today);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          {timeOfDay ? `Good ${timeOfDay}` : "Welcome"}, {student?.student?.first_name || user?.full_name?.split(" ")[0]} 👋
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          {student?.class?.name ? `${student.class.name} · ` : ""}
          {student?.class?.academic_year || "Fairview School"}
        </p>
      </div>

      {/* Hero — up next */}
      <div className={cn(
        "rounded-2xl p-6 mb-6 text-white shadow-lg",
        nextSlot ? "bg-gradient-to-br from-brand-600 via-brand-700 to-brand-900" : "bg-gradient-to-br from-slate-600 to-slate-800",
      )}>
        <div className="flex items-start gap-5">
          <div className="w-14 h-14 rounded-xl bg-white/10 backdrop-blur flex items-center justify-center shrink-0">
            <Clock size={22} />
          </div>
          <div className="flex-1">
            <p className="text-xs font-bold uppercase tracking-widest text-white/70 mb-1">Up next</p>
            {nextSlot ? (
              <>
                <h2 className="text-xl font-black tracking-tight">{nextSlot.subject_name ?? "Lesson"}</h2>
                <p className="text-sm text-white/80 mt-1">
                  {nextSlot.start_time}–{nextSlot.end_time}
                  {nextSlot.room ? ` · Room ${nextSlot.room}` : ""}
                </p>
              </>
            ) : (
              <>
                <h2 className="text-xl font-black tracking-tight">No more lessons today</h2>
                <p className="text-sm text-white/80 mt-1">Enjoy the rest of your day.</p>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          icon={Calendar}
          iconClass="bg-emerald-50 text-emerald-600"
          label="Attendance"
          value={stats?.attendance_pct != null ? `${stats.attendance_pct}%` : "—"}
          sublabel={stats?.attendance_days ? `over ${stats.attendance_days} days` : null}
        />
        <StatCard
          icon={BookOpen}
          iconClass="bg-amber-50 text-amber-600"
          label="Assignments"
          value={stats?.pending_assignments ?? 0}
          sublabel="pending"
          highlight={!!stats?.pending_assignments}
        />
        <StatCard
          icon={CheckSquare}
          iconClass="bg-indigo-50 text-indigo-600"
          label="Lessons Today"
          value={today.length}
          sublabel={today.length === 1 ? "1 lesson" : null}
        />
      </div>

      {/* Today's schedule */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden mt-6">
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-800">Today's Classes</h3>
            <p className="text-xs text-slate-400 mt-0.5">{DAYS_SHORT[(new Date().getDay() + 6) % 7]}</p>
          </div>
          <Link href="/dashboard/my-timetable" className="text-xs text-brand-600 font-semibold hover:underline flex items-center gap-1">
            Full timetable <ArrowRight size={12} />
          </Link>
        </div>
        <div className="divide-y divide-slate-50">
          {today.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-slate-400">
              No classes scheduled for today.
            </div>
          ) : (
            today.map((slot) => (
              <div key={slot.id} className="px-5 py-3.5 flex items-center gap-4">
                <div className="text-xs font-bold text-slate-500 tabular-nums w-20">
                  {slot.start_time}–{slot.end_time}
                </div>
                <div className="w-1 h-10 rounded bg-indigo-400" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-slate-900 truncate">{slot.subject_name ?? "Lesson"}</p>
                  <p className="text-xs text-slate-500 truncate">{slot.room ? `Room ${slot.room}` : "—"}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
        <QuickTile href="/dashboard/modules/school/eclassroom" icon={BookOpen} label="Assignments" color="bg-amber-500" />
        <QuickTile href="/dashboard/modules/school/cbt" icon={MonitorCheck} label="CBT Tests" color="bg-indigo-500" />
        <QuickTile href="/dashboard/my-library" icon={Library} label="My Library" color="bg-rose-500" />
        <QuickTile href="/dashboard/my-timetable" icon={Calendar} label="My Timetable" color="bg-emerald-500" />
      </div>

      {/* School news feed — read-only; students see the same org-wide announcements. */}
      <div className="mt-8">
        <div className="flex items-center gap-2 mb-3">
          <Newspaper size={16} className="text-indigo-600" />
          <h2 className="text-sm font-bold text-slate-800">News Feed</h2>
        </div>
        <NewsFeed limit={20} showComposer={false} />
      </div>
    </div>
  );
}

function getNextSlot(slots: ContextSlot[]): ContextSlot | null {
  if (!slots.length) return null;
  const now = new Date();
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const ordered = [...slots].sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""));
  const upcoming = ordered.find((s) => toMin(s.start_time) >= nowMin);
  return upcoming ?? null;
}

function toMin(t: string): number {
  const [h, m] = (t || "0:0").split(":").map((n) => parseInt(n, 10) || 0);
  return h * 60 + m;
}

function StatCard({
  icon: Icon, iconClass, label, value, sublabel, highlight = false,
}: {
  icon: typeof Clock;
  iconClass: string;
  label: string;
  value: number | string;
  sublabel?: string | null;
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
      {sublabel && <p className="text-[10px] text-slate-400 mt-0.5">{sublabel}</p>}
    </div>
  );
}

function QuickTile({
  href, icon: Icon, label, color,
}: {
  href: string;
  icon: typeof Clock;
  label: string;
  color: string;
}) {
  return (
    <Link
      href={href}
      className="group bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md hover:-translate-y-0.5 transition-all"
    >
      <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center text-white mb-3", color)}>
        <Icon size={15} />
      </div>
      <p className="text-sm font-bold text-slate-800">{label}</p>
    </Link>
  );
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
