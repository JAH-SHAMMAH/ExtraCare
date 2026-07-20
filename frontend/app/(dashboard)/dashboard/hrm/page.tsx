"use client";

import { useRef } from "react";
import Link from "next/link";
import {
  Users, UserCircle, Cake, Gavel,
  PieChart as PieChartIcon, Building2, BarChart3, CalendarClock,
  Briefcase, ShieldAlert, Star, ShieldCheck, ChevronLeft, ChevronRight,
} from "lucide-react";
import { HR_QUICK_LINKS, quickLinkTarget } from "@/components/hrm/hrNav";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { useHrOverview, useHrBirthdays } from "@/hooks/useHrm";
import { useLeaveAnalytics } from "@/hooks/useLeave";
import { useHrStats } from "@/hooks/useHrExtended";
import { BirthdayPopup } from "@/components/hr/BirthdayPopup";

const PIE_COLORS = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#64748b"];

export default function HrDashboardPage() {
  const { data: overview, isLoading: ovLoading } = useHrOverview();
  const { data: birthdays = [] } = useHrBirthdays();
  const { data: leave } = useLeaveAnalytics();
  const { data: stats, isLoading: statsLoading } = useHrStats();

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <BirthdayPopup />

      <header>
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Modules</span><span>/</span>
          <span className="text-brand-600 font-semibold">HR Manager</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">HR Manager Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">People metrics, events, and quick actions — all live from your org.</p>
      </header>

      {/* Quick Links — all HR categories, horizontally scrollable (Educare parity).
          Each card opens the section page with that tab's dropdown pre-expanded. */}
      <QuickLinksRow />

      {/* Overview cards — Educare parity (Jobs Opening + Disciplinary now wired via /hr/stats) */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Total Active Staff" value={overview?.total_active_staff} loading={ovLoading} icon={Users} />
        <MetricCard label="Jobs Opening" value={stats?.open_jobs} loading={statsLoading} icon={Briefcase} href="/dashboard/hrm/recruitment" />
        <MetricCard label="Disciplinary Cases" value={stats?.open_disciplinary} loading={statsLoading} icon={ShieldAlert} href="/dashboard/hrm/disciplinary" />
        <MetricCard label="Leave Applications" value={leave?.pending_count ?? 0} loading={false} icon={CalendarClock} href="/dashboard/hrm/leave/admin" />
      </section>

      {/* Charts */}
      <section className="grid lg:grid-cols-3 gap-4">
        <ChartCard title="Staff per Department" icon={Building2}>
          {overview && overview.staff_per_department.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={overview.staff_per_department}>
                <XAxis dataKey="department" tick={{ fontSize: 11 }} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty text="No department data yet." />
          )}
        </ChartCard>

        <ChartCard title="Gender Distribution" icon={PieChartIcon}>
          {overview && overview.gender_distribution.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={overview.gender_distribution}
                  dataKey="count"
                  nameKey="label"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={(e: any) => `${e.label}: ${e.count}`}
                  fontSize={11}
                >
                  {overview.gender_distribution.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <Empty text="Gender data will appear once staff fill profiles." />
          )}
        </ChartCard>

        <ChartCard title="Age Distribution" icon={BarChart3}>
          {overview && overview.age_distribution.some((a) => a.count > 0) ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={overview.age_distribution}>
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <Empty text="Age data will appear once staff add their DOB." />
          )}
        </ChartCard>
      </section>

      {/* Leave analytics (admins only — hook returns no data for unprivileged users) */}
      {leave && (
        <section className="grid lg:grid-cols-3 gap-4">
          <ChartCard title="Total Leave per Month" icon={BarChart3}>
            {leave.by_month.some((m) => m.count > 0) ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={leave.by_month}>
                  <XAxis dataKey="month" tick={{ fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={55} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty text="No leave has been logged in the last 12 months." />
            )}
          </ChartCard>

          <ChartCard title="Leave Analysis (by Type)" icon={PieChartIcon}>
            {leave.by_type.some((t) => t.count > 0) ? (
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={leave.by_type.filter((t) => t.count > 0)}
                    dataKey="count"
                    nameKey="leave_type"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    label={(e: any) => `${e.leave_type}: ${e.count}`}
                    fontSize={11}
                  >
                    {leave.by_type
                      .filter((t) => t.count > 0)
                      .map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <Empty text="No leave applications yet." />
            )}
          </ChartCard>

          <ChartCard title="Status Breakdown" icon={CalendarClock}>
            {leave.total > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={leave.by_status}>
                  <XAxis dataKey="status" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Empty text="No leave applications yet." />
            )}
          </ChartCard>
        </section>
      )}

      {/* Birthdays + Events now live on the main /dashboard — see
          PeoplePulse. Keeping them here duplicated the data and created
          drift risk, so HRM focuses on HR-specific analytics only. */}
    </div>
  );
}

// ── Primitives ───────────────────────────────────────────────────────────────

const QL_TINTS = [
  "bg-indigo-50 text-indigo-600", "bg-sky-50 text-sky-600", "bg-amber-50 text-amber-600",
  "bg-teal-50 text-teal-600", "bg-orange-50 text-orange-600", "bg-emerald-50 text-emerald-600",
  "bg-purple-50 text-purple-600", "bg-rose-50 text-rose-600", "bg-slate-100 text-slate-600",
];

function QuickLinksRow() {
  const ref = useRef<HTMLDivElement>(null);
  const scroll = (dir: number) => ref.current?.scrollBy({ left: dir * 320, behavior: "smooth" });
  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-bold text-slate-800">Quick Links</h2>
        <div className="flex gap-1">
          <button onClick={() => scroll(-1)} aria-label="Scroll left" className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100"><ChevronLeft size={15} /></button>
          <button onClick={() => scroll(1)} aria-label="Scroll right" className="p-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-100"><ChevronRight size={15} /></button>
        </div>
      </div>
      <div ref={ref} className="flex gap-3 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {HR_QUICK_LINKS.map((q, i) => (
          <Link key={q.key} href={quickLinkTarget(q.key)}
            className="shrink-0 w-44 bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md hover:border-brand-300 transition-all flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${QL_TINTS[i % QL_TINTS.length]}`}>
              <q.icon className="w-5 h-5" />
            </div>
            <span className="text-sm font-semibold text-slate-800">{q.label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function MetricCard({
  label, value, loading, icon: Icon, href,
}: { label: string; value: number | undefined; loading: boolean; icon: any; href?: string }) {
  const inner = (
    <>
      <div className="flex items-center gap-2 text-slate-500 mb-2">
        <Icon className="w-4 h-4" />
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-black text-slate-900">
        {loading ? <span className="inline-block w-10 h-6 bg-slate-100 animate-pulse rounded" /> : (value ?? 0)}
      </div>
    </>
  );
  const base = "bg-white rounded-xl border border-slate-200 p-4";
  return href ? (
    <Link href={href} className={`${base} block hover:shadow-md transition-shadow`}>{inner}</Link>
  ) : (
    <div className={base}>{inner}</div>
  );
}

function ChartCard({ title, icon: Icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <header className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-brand-600" />
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      </header>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-slate-500 italic py-6 text-center">{text}</p>;
}
