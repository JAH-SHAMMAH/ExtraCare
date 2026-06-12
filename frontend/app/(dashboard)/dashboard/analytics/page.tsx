"use client";

import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/lib/api";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { BarChart3, Briefcase, Users, GraduationCap, Heart, TrendingUp } from "lucide-react";

export default function AnalyticsPage() {
  const { data: overview, isLoading } = useQuery({
    queryKey: ["analytics", "overview"],
    queryFn: analyticsApi.overview,
    refetchInterval: 30_000,
  });

  const modules = new Set<string>(overview?.workspace?.modules_enabled ?? []);
  const cards = [
    { label: "Total Users", value: overview?.users?.total, icon: Users, color: "text-blue-600 bg-blue-50" },
    { label: "Active Users", value: overview?.users?.active, icon: TrendingUp, color: "text-emerald-600 bg-emerald-50" },
    { label: "Online Today", value: overview?.users?.online_today, icon: Users, color: "text-violet-600 bg-violet-50" },
    { label: "Students", value: overview?.school?.total_students, icon: GraduationCap, color: "text-purple-600 bg-purple-50", module: "school" },
    { label: "Attendance Today", value: overview?.school?.attendance_today, icon: GraduationCap, color: "text-cyan-600 bg-cyan-50", module: "school" },
    { label: "Total Patients", value: overview?.hospital?.total_patients, icon: Heart, color: "text-rose-600 bg-rose-50", module: "hospital" },
    { label: "Appointments Today", value: overview?.hospital?.appointments_today, icon: Heart, color: "text-pink-600 bg-pink-50", module: "hospital" },
    { label: "Employees", value: overview?.business?.total_employees, icon: Briefcase, color: "text-emerald-600 bg-emerald-50", module: "business" },
  ].filter((card) => !card.module || modules.has(card.module));

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Core</span><span>/</span>
          <span className="text-brand-600 font-semibold">Analytics</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Analytics</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {overview?.workspace?.label ?? "Organization"} overview &middot; {overview?.period?.start} to {overview?.period?.end}
        </p>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</p>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${color}`}>
                <Icon size={14} />
              </div>
            </div>
            {isLoading ? (
              <div className="h-7 w-16 bg-slate-100 rounded animate-pulse" />
            ) : (
              <p className="text-2xl font-black text-slate-900">{value ?? 0}</p>
            )}
          </div>
        ))}
      </div>

      {/* Activity feed */}
      <div className="max-w-3xl">
        <h2 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
          <BarChart3 size={15} /> Recent Activity
        </h2>
        <ActivityFeed />
      </div>
    </div>
  );
}
