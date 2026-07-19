"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight, Calendar, BookOpen, GraduationCap, Award, Clock, AlertCircle, Newspaper,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { PageHeaderSkeleton, CardGridSkeleton } from "@/components/loading/Skeleton";
import { NewsFeed } from "@/components/feed/NewsFeed";
import { cn, getInitials } from "@/lib/utils";

export function ParentHome() {
  const { user, org } = useAuthStore();
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const [timeOfDay, setTimeOfDay] = useState("");

  useEffect(() => {
    setTimeOfDay(getTimeOfDay());
  }, []);

  if (showSkeleton) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <PageHeaderSkeleton />
        <CardGridSkeleton count={2} />
      </div>
    );
  }

  const children = data?.as_parent?.children ?? [];

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          {timeOfDay ? `Good ${timeOfDay}` : "Welcome"}, {user?.full_name?.split(" ")[0]} 👋
        </h1>
        <p className="text-slate-500 text-sm mt-1">
          {org?.name} · {children.length === 0 ? "No children linked yet" : children.length === 1 ? `Following ${children[0].first_name}` : `Following ${children.length} children`}
        </p>
      </div>

      {children.length === 0 ? (
        <EmptyState />
      ) : (
        <div className={cn(
          "grid gap-5",
          children.length === 1 ? "grid-cols-1 max-w-2xl" : "grid-cols-1 md:grid-cols-2",
        )}>
          {children.map((c) => <ChildCard key={c.id} child={c} />)}
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-8">
        <QuickTile href="/dashboard/my-children" icon={GraduationCap} label="All Children" color="bg-brand-600" />
        <QuickTile href="/dashboard/modules/school/fees" icon={Award} label="Fees" color="bg-amber-500" />
        <QuickTile href="/dashboard/modules/school/attendance" icon={Calendar} label="Attendance" color="bg-emerald-500" />
        <QuickTile href="/dashboard/modules/school/feedback" icon={BookOpen} label="Send Feedback" color="bg-indigo-500" />
      </div>

      {/* School news feed — the same org-wide announcements staff see. */}
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

// ── Child card ────────────────────────────────────────────────────────────────

function ChildCard({ child }: { child: ParentChild }) {
  const att = child.stats.attendance_pct;
  const attColor = att == null ? "text-slate-400" : att >= 90 ? "text-emerald-600" : att >= 75 ? "text-amber-600" : "text-rose-600";

  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="px-5 py-4 flex items-center gap-4 border-b border-slate-100">
        <div className="w-12 h-12 rounded-xl bg-brand-600 flex items-center justify-center text-white font-black text-sm shrink-0 overflow-hidden">
          {child.photo_url ? (
            <img src={child.photo_url} alt="" className="w-full h-full object-cover" />
          ) : (
            getInitials(`${child.first_name} ${child.last_name}`)
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-black text-slate-900 truncate">
            {child.first_name} {child.last_name}
          </p>
          <p className="text-xs text-slate-500 truncate">
            {child.class_name ?? "No class"} · {child.student_id}
          </p>
        </div>
        {child.is_primary && (
          <span className="badge bg-brand-50 text-brand-700 border-brand-200 text-[10px]">Primary</span>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100">
        <div className="px-4 py-3 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Attendance</p>
          <p className={cn("text-lg font-black tabular-nums", attColor)}>
            {att != null ? `${att}%` : "—"}
          </p>
        </div>
        <div className="px-4 py-3 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Assignments</p>
          <p className="text-lg font-black text-slate-900 tabular-nums">
            {child.stats.pending_assignments}
          </p>
        </div>
        <div className="px-4 py-3 text-center">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Latest Grade</p>
          <p className="text-lg font-black text-slate-900">
            {child.stats.latest_grade_letter ?? "—"}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="divide-y divide-slate-50">
        <ActionRow href="/dashboard/modules/school/attendance" icon={Calendar} label="Attendance history" />
        <ActionRow href="/dashboard/modules/school/grades" icon={GraduationCap} label="Grades & reports" />
        <ActionRow href="/dashboard/modules/school/fees" icon={Award} label="Fees & invoices" />
      </div>
    </div>
  );
}

function ActionRow({
  href, icon: Icon, label,
}: { href: string; icon: typeof Clock; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50 transition-colors group"
    >
      <Icon size={14} className="text-slate-400 group-hover:text-brand-600" />
      <span className="flex-1 text-sm font-medium text-slate-700">{label}</span>
      <ArrowRight size={14} className="text-slate-300 group-hover:text-brand-500" />
    </Link>
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

function EmptyState() {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center">
      <div className="w-14 h-14 rounded-2xl bg-amber-50 flex items-center justify-center mx-auto mb-4">
        <AlertCircle size={26} className="text-amber-500" />
      </div>
      <h2 className="text-base font-bold text-slate-800 mb-1">No children linked to your account</h2>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        Ask the school administrator to link your parent account to your child's student record so you can follow attendance, grades, and fees here.
      </p>
    </div>
  );
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
