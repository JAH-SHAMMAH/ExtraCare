"use client";

import Link from "next/link";
import { Calendar, GraduationCap, Award, ArrowRight, AlertCircle, Users, Smile } from "lucide-react";
import { useMyContexts, type ParentChild } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { PageHeaderSkeleton, TableSkeleton } from "@/components/loading/Skeleton";
import { cn, getInitials } from "@/lib/utils";

/**
 * Parent portal: full list of the authenticated user's children with
 * per-child attendance, pending assignments, latest grade, and drill-down
 * actions to attendance/grades/fees for each.
 *
 * Data source: `/me/contexts` (the same call that powers the ParentHome
 * header cards). Keeping both views on one payload means a role switch
 * never refetches; the parent is instant.
 */
export default function MyChildrenPage() {
  const { data, isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(isLoading);
  const children = data?.as_parent?.children ?? [];

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Parent portal</span><span>/</span>
          <span className="text-brand-600 font-semibold">My Children</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Children</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Attendance, grades, and fees for the children linked to your account.
        </p>
      </div>

      {showSkeleton ? (
        <TableSkeleton rows={3} cols={5} />
      ) : children.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {children.map((c) => <ChildRow key={c.id} child={c} />)}
        </div>
      )}
    </div>
  );
}

function ChildRow({ child }: { child: ParentChild }) {
  const att = child.stats.attendance_pct;
  const attColor = att == null ? "text-slate-400" : att >= 90 ? "text-emerald-600" : att >= 75 ? "text-amber-600" : "text-rose-600";

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-5 py-4 flex items-center gap-4 border-b border-slate-100">
        <div className="w-12 h-12 rounded-xl bg-brand-600 flex items-center justify-center text-white font-black text-sm overflow-hidden shrink-0">
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
            {child.class_name ?? "No class"} · {child.student_id} · {child.relationship}
          </p>
        </div>
        {child.is_primary && (
          <span className="badge bg-brand-50 text-brand-700 border-brand-200 text-[10px]">Primary guardian</span>
        )}
      </div>

      <div className="grid grid-cols-3 divide-x divide-slate-100 border-b border-slate-100">
        <StatCell label="Attendance" value={att != null ? `${att}%` : "—"} color={attColor} />
        <StatCell label="Assignments pending" value={String(child.stats.pending_assignments)} color="text-slate-900" />
        <StatCell
          label="Latest grade"
          value={child.stats.latest_grade_letter ?? "—"}
          sublabel={child.stats.latest_grade_score != null ? `${child.stats.latest_grade_score}/100` : null}
          color="text-slate-900"
        />
      </div>

      <div className="flex flex-wrap divide-x divide-slate-50">
        <LinkCell href="/dashboard/my-children/attendance" icon={Calendar} label="Attendance history" />
        <LinkCell href="/dashboard/my-children/report-card" icon={GraduationCap} label="Grades & reports" />
        <LinkCell href="/dashboard/my-children/daily-reports" icon={Smile} label="Daily reports" />
        <LinkCell href="/dashboard/my-children/payments" icon={Award} label="Fees & invoices" />
      </div>
    </div>
  );
}

function StatCell({
  label, value, color, sublabel,
}: { label: string; value: string; color: string; sublabel?: string | null }) {
  return (
    <div className="px-4 py-3 text-center">
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">{label}</p>
      <p className={cn("text-lg font-black tabular-nums", color)}>{value}</p>
      {sublabel && <p className="text-[10px] text-slate-400 mt-0.5">{sublabel}</p>}
    </div>
  );
}

function LinkCell({ href, icon: Icon, label }: { href: string; icon: typeof Calendar; label: string }) {
  return (
    <Link
      href={href}
      className="flex-1 flex items-center justify-center gap-2 px-4 py-3 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-brand-700 transition-colors"
    >
      <Icon size={13} />
      {label}
      <ArrowRight size={11} className="opacity-50" />
    </Link>
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
        A school administrator needs to link your account to your child&apos;s student record before you can follow their progress.
      </p>
    </div>
  );
}
