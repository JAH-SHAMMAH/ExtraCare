"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { SchoolWidgets } from "@/components/dashboard/widgets/SchoolWidgets";
import { ClassDistributionChart } from "@/components/dashboard/ClassDistributionChart";
import { PeoplePulse } from "@/components/dashboard/PeoplePulse";
import { useAuthStore } from "@/lib/store";
import { useExecutiveOverview, useWorkspaceOverview, type ExecutiveOverview, type WorkspaceOverview } from "@/hooks/useDashboard";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { moduleAllowedForOrg } from "@/lib/workspace";
import { Skeleton } from "@/components/loading/Skeleton";
import {
  Users, GraduationCap, Heart, TrendingUp, AlertCircle,
  School as SchoolIcon, UserCheck, ClipboardCheck, Bus,
  MessageSquare, AlertTriangle, ArrowUpRight,
  CheckCircle2, RefreshCw, Loader2, User as UserIcon, UserCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Executive Dashboard (Phase 6.8). One-screen control centre that answers:
 *   - How many students do we have? (total, male, female)
 *   - How many classes / teachers?
 *   - What's attendance today?
 *   - Are transport ops healthy right now?
 *   - Is communications (SMS) working today?
 *
 * All numbers come from a single backend call. The layout is two strips:
 *   1. Primary (six prominent cards) — the non-negotiable headline numbers
 *   2. Secondary insights — Transport + SMS at-a-glance
 * Followed by the existing ActivityFeed / QuickActions / PeoplePulse below.
 */
export function AdminHome() {
  const { user, org } = useAuthStore();
  const [timeOfDay, setTimeOfDay] = useState("");
  const [dateStr, setDateStr] = useState("");

  useEffect(() => {
    setTimeOfDay(getTimeOfDay());
    setDateStr(new Date().toLocaleDateString("en-GB", {
      weekday: "long", day: "numeric", month: "long", year: "numeric",
    }));
  }, []);

  const hasOrg = !!org;
  const isSchoolWorkspace = hasOrg && moduleAllowedForOrg(org, "school");
  const schoolOverview = useExecutiveOverview(isSchoolWorkspace);
  const workspaceOverview = useWorkspaceOverview(hasOrg && !isSchoolWorkspace);
  const data = schoolOverview.data;
  const workspaceData = workspaceOverview.data;
  const isLoading = isSchoolWorkspace ? schoolOverview.isLoading : workspaceOverview.isLoading;
  const isFetching = isSchoolWorkspace ? schoolOverview.isFetching : workspaceOverview.isFetching;
  const refetch = isSchoolWorkspace ? schoolOverview.refetch : workspaceOverview.refetch;
  const showSkeleton = useDelayedFlag(isLoading);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-end justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            {timeOfDay ? `Good ${timeOfDay}` : "Welcome"}, {user?.full_name?.split(" ")[0]} 👋
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            {org?.name}{dateStr ? ` · ${dateStr}` : ""}
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary gap-2 text-xs py-1.5"
          title="Refresh dashboard"
        >
          {isFetching ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          Refresh
        </button>
      </div>

      {/* Primary stats strip — 6 prominent cards */}
      {isSchoolWorkspace ? (
        <>
          <PrimaryStrip data={data} loading={showSkeleton} />

      {/* Secondary insights row — Transport + SMS */}
          <SecondaryRow data={data} loading={showSkeleton} />

      {/* School class distribution (students per class · current session / all sessions) */}
          <div className="mt-4">
            <ClassDistributionChart />
          </div>

      {/* Module-specific widgets (school) */}
          <div className="mt-8">
            <SchoolWidgets />
          </div>
        </>
      ) : (
        <WorkspaceStrip data={workspaceData} loading={showSkeleton} />
      )}

      {/* Activity + Quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        <div className="lg:col-span-2">
          <ActivityFeed />
        </div>
        <div className="space-y-4">
          {isSchoolWorkspace ? (
            <QuickActions modules={org?.modules_enabled || []} />
          ) : (
            <WorkspaceQuickActions data={workspaceData} loading={showSkeleton} />
          )}
        </div>
      </div>

      {/* People pulse */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PeoplePulse variant="stacked" />
      </div>
    </div>
  );
}

// ── Primary stats strip ──────────────────────────────────────────────────────

function PrimaryStrip({
  data, loading,
}: { data: ExecutiveOverview | undefined; loading: boolean }) {
  const cards: Array<{
    label: string;
    value: number | string;
    sub: string | null;
    icon: typeof Users;
    accent: string;
    iconBg: string;
  }> = [
    {
      label: "Active Students",
      value: data?.students.total ?? "—",
      sub: data ? `${data.students.male + data.students.female} with gender on file` : null,
      icon: GraduationCap,
      accent: "text-brand-700",
      iconBg: "bg-brand-50 text-brand-600",
    },
    {
      label: "Male",
      value: data?.students.male ?? "—",
      sub: data && data.students.total ? `${pct(data.students.male, data.students.total)}% of roster` : null,
      icon: UserIcon,
      accent: "text-sky-700",
      iconBg: "bg-sky-50 text-sky-600",
    },
    {
      label: "Female",
      value: data?.students.female ?? "—",
      sub: data && data.students.total ? `${pct(data.students.female, data.students.total)}% of roster` : null,
      icon: UserCircle,
      accent: "text-rose-700",
      iconBg: "bg-rose-50 text-rose-600",
    },
    {
      label: "Classes",
      value: data?.classes ?? "—",
      sub: data?.classes ? "Across the school" : null,
      icon: SchoolIcon,
      accent: "text-indigo-700",
      iconBg: "bg-indigo-50 text-indigo-600",
    },
    {
      label: "Teachers",
      value: data?.teachers ?? "—",
      sub: data?.teachers ? "On staff" : null,
      icon: UserCheck,
      accent: "text-emerald-700",
      iconBg: "bg-emerald-50 text-emerald-600",
    },
    {
      label: "Attendance Today",
      value: data?.attendance_today ?? "—",
      sub: data && data.students.total
        ? `${pct(data.attendance_today, data.students.total)}% present`
        : null,
      icon: ClipboardCheck,
      accent: "text-amber-700",
      iconBg: "bg-amber-50 text-amber-600",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
      {cards.map((c, i) => (
        <PrimaryCard key={i} {...c} loading={loading} />
      ))}
    </div>
  );
}

function PrimaryCard({
  label, value, sub, icon: Icon, accent, iconBg, loading,
}: {
  label: string;
  value: number | string;
  sub: string | null;
  icon: typeof Users;
  accent: string;
  iconBg: string;
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200/70 p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between mb-3">
        <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center", iconBg)}>
          <Icon size={16} />
        </div>
        <ArrowUpRight size={12} className="text-slate-300" />
      </div>
      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-7 w-16 rounded-lg" />
          <Skeleton className="h-2.5 w-24" />
        </div>
      ) : (
        <>
          <p className={cn("text-2xl font-black tracking-tight tabular-nums", accent)}>
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-1">
            {label}
          </p>
          {sub && <p className="text-[10px] text-slate-400 mt-1 truncate">{sub}</p>}
        </>
      )}
    </div>
  );
}

// ── Secondary insights row ──────────────────────────────────────────────────

function SecondaryRow({
  data, loading,
}: { data: ExecutiveOverview | undefined; loading: boolean }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
      <TransportInsight data={data} loading={loading} />
      <SmsInsight data={data} loading={loading} />
    </div>
  );
}

function TransportInsight({
  data, loading,
}: { data: ExecutiveOverview | undefined; loading: boolean }) {
  const t = data?.transport;
  const hasIssues = (t?.issues ?? 0) > 0;

  return (
    <Link
      href="/dashboard/modules/school/transport"
      className={cn(
        "block bg-white rounded-xl border p-5 hover:shadow-md transition-all group",
        hasIssues ? "border-rose-200 ring-1 ring-rose-100" : "border-slate-200/70",
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center",
            hasIssues ? "bg-rose-50 text-rose-600" : "bg-emerald-50 text-emerald-600",
          )}>
            <Bus size={16} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">Transport</p>
            <p className="text-[10px] text-slate-400">Live operations</p>
          </div>
        </div>
        <ArrowUpRight size={14} className="text-slate-300 group-hover:text-slate-600" />
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          <MiniStat
            label="Active trips"
            value={t?.active_trips ?? 0}
            sub={t?.trips_planned ? `${t.trips_planned} planned` : null}
          />
          <MiniStat
            label="On board now"
            value={t?.students_on_board ?? 0}
            sub={t?.students_on_board ? "Students en route" : null}
          />
          <MiniStat
            label="Issues"
            value={t?.issues ?? 0}
            danger={hasIssues}
            sub={hasIssues
              ? issueBreakdownLabel(t?.issue_breakdown)
              : "All running smoothly"}
          />
        </div>
      )}
    </Link>
  );
}

function SmsInsight({
  data, loading,
}: { data: ExecutiveOverview | undefined; loading: boolean }) {
  const s = data?.sms;
  const hasFailures = (s?.failed_today ?? 0) > 0;

  return (
    <Link
      href="/dashboard/modules/school/sms"
      className={cn(
        "block bg-white rounded-xl border p-5 hover:shadow-md transition-all group",
        hasFailures ? "border-amber-200 ring-1 ring-amber-100" : "border-slate-200/70",
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={cn(
            "w-9 h-9 rounded-lg flex items-center justify-center",
            hasFailures ? "bg-amber-50 text-amber-600" : "bg-indigo-50 text-indigo-600",
          )}>
            <MessageSquare size={16} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">SMS today</p>
            <p className="text-[10px] text-slate-400">Communications</p>
          </div>
        </div>
        <ArrowUpRight size={14} className="text-slate-300 group-hover:text-slate-600" />
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-12 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3">
          <MiniStat
            label="Sent"
            value={s?.sent_today ?? 0}
            sub={s?.campaigns_today ? `${s.campaigns_today} campaign${s.campaigns_today === 1 ? "" : "s"}` : null}
          />
          <MiniStat
            label="Delivered"
            value={s?.delivered_today ?? 0}
            success={(s?.delivered_today ?? 0) > 0}
            sub={s && s.sent_today
              ? `${pct(s.delivered_today, s.sent_today)}% delivery`
              : null}
          />
          <MiniStat
            label="Failed"
            value={s?.failed_today ?? 0}
            warning={hasFailures}
            sub={hasFailures ? "Check delivery logs" : "All delivered"}
          />
        </div>
      )}
    </Link>
  );
}

function MiniStat({
  label, value, sub, danger = false, warning = false, success = false,
}: {
  label: string;
  value: number;
  sub: string | null;
  danger?: boolean;
  warning?: boolean;
  success?: boolean;
}) {
  return (
    <div>
      <p className={cn(
        "text-2xl font-black tabular-nums",
        danger ? "text-rose-700"
        : warning ? "text-amber-700"
        : success ? "text-emerald-700"
        : "text-slate-900",
      )}>
        {value.toLocaleString()}
      </p>
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-0.5">
        {label}
      </p>
      {sub && <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">{sub}</p>}
    </div>
  );
}

function issueBreakdownLabel(b: ExecutiveOverview["transport"]["issue_breakdown"] | undefined): string {
  if (!b) return "Needs attention";
  const parts: string[] = [];
  if (b.skipped) parts.push(`${b.skipped} skipped`);
  if (b.cancelled) parts.push(`${b.cancelled} cancelled`);
  if (b.running_long) parts.push(`${b.running_long} running long`);
  return parts.length ? parts.join(" · ") : "Needs attention";
}

// ── Quick Actions / Onboarding empty state (preserved from prior) ───────────

function WorkspaceStrip({
  data,
  loading,
}: {
  data: WorkspaceOverview | undefined;
  loading: boolean;
}) {
  const cards = data?.cards ?? [];

  return (
    <div>
      <div className="mb-4">
        <p className="text-xs font-bold uppercase tracking-widest text-slate-400">
          {data?.workspace.label ?? "Workspace"} overview
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {(loading ? Array.from({ length: 4 }) : cards).map((card: any, i) => (
          <Link
            key={card?.href ?? i}
            href={card?.href ?? "/dashboard"}
            className="bg-white rounded-xl border border-slate-200/70 p-5 shadow-sm hover:shadow-md transition-shadow group min-h-32"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-9 h-9 rounded-lg bg-slate-50 text-slate-600 flex items-center justify-center">
                <Users size={16} />
              </div>
              <ArrowUpRight size={13} className="text-slate-300 group-hover:text-slate-600" />
            </div>
            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-7 w-20 rounded-lg" />
                <Skeleton className="h-3 w-28" />
              </div>
            ) : (
              <>
                <p className="text-2xl font-black tracking-tight tabular-nums text-slate-900">
                  {formatMetric(card.value)}
                </p>
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mt-1">
                  {card.label}
                </p>
                {card.sub && <p className="text-[10px] text-slate-400 mt-1 line-clamp-1">{card.sub}</p>}
              </>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}

function WorkspaceQuickActions({
  data,
  loading,
}: {
  data: WorkspaceOverview | undefined;
  loading: boolean;
}) {
  const actions = data?.quick_actions ?? [];

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h3 className="text-sm font-bold text-slate-800 mb-4">Quick Actions</h3>
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 rounded-lg" />)}
        </div>
      ) : (
        <div className="space-y-2">
          {actions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 text-sm font-medium transition-all group"
            >
              <ArrowUpRight size={15} className="group-hover:text-brand-600" />
              {action.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function formatMetric(value: number | string): string {
  if (typeof value === "number") return value.toLocaleString();
  return value;
}

function QuickActions({ modules }: { modules: string[] }) {
  const actions = [
    { label: "Add User", href: "/dashboard/users?new=1", icon: Users, show: true },
    { label: "New Student", href: "/dashboard/modules/school/students?new=1", icon: GraduationCap, show: modules.includes("school") },
    { label: "Send SMS", href: "/dashboard/modules/school/sms", icon: MessageSquare, show: modules.includes("school") },
    { label: "Run Payroll", href: "/dashboard/modules/business/payroll?run=1", icon: TrendingUp, show: modules.includes("hr") },
  ].filter((a) => a.show);

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <h3 className="text-sm font-bold text-slate-800 mb-4">Quick Actions</h3>
      <div className="space-y-2">
        {actions.map(({ label, href, icon: Icon }) => (
          <a
            key={href}
            href={href}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-slate-50 hover:bg-brand-50 hover:text-brand-700 text-slate-600 text-sm font-medium transition-all group"
          >
            <Icon size={15} className="group-hover:text-brand-600" />
            {label}
          </a>
        ))}
      </div>
    </div>
  );
}

export function OnboardingEmptyState({ orgName }: { orgName: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-brand-50 flex items-center justify-center mb-5">
        <AlertCircle size={26} className="text-brand-600" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Welcome to {orgName}</h1>
      <p className="text-sm text-slate-500 max-w-md mb-6">
        The school dashboard isn&apos;t set up yet. A school administrator needs
        to finish configuration before the dashboard becomes useful.
      </p>
      <a
        href="mailto:admin@fairviewschoolng.com?subject=Portal%20setup"
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-semibold hover:bg-brand-700 transition"
      >
        Contact the school administrator
      </a>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function pct(part: number, whole: number): number {
  if (!whole) return 0;
  return Math.round((part / whole) * 100);
}

function getTimeOfDay(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 17) return "afternoon";
  return "evening";
}
