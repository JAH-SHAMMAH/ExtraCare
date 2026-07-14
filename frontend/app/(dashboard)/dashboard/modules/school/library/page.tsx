"use client";

import { useState } from "react";
import { BookOpen, Clock, AlertTriangle } from "lucide-react";
import { useLibraryStats, type LibraryBookRow } from "@/hooks/useSchool";
import { StatCard, CatalogueTab, IssueLoanDrawer } from "./_components";

/**
 * Library — Admin Dashboard. At-a-glance counters + the inventory browse (the
 * catalogue, read-only + issue). Full book management lives on Manage Catalogue.
 */
export default function LibraryDashboardPage() {
  const { data: stats } = useLibraryStats();
  const [issueTarget, setIssueTarget] = useState<LibraryBookRow | null>(null);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">Admin Dashboard</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Library — Admin Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">Collection at a glance, plus the inventory browse.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="Titles" value={stats?.total_books ?? "—"} color="bg-brand-50 text-brand-700" icon={BookOpen} />
        <StatCard label="Total Copies" value={stats?.total_copies ?? "—"} color="bg-indigo-50 text-indigo-700" icon={BookOpen} />
        <StatCard label="Checked Out" value={stats?.loans_out ?? "—"} color="bg-amber-50 text-amber-700" icon={Clock} />
        <StatCard label="Overdue" value={stats?.overdue ?? "—"} color={stats?.overdue ? "bg-rose-50 text-rose-700" : "bg-slate-50 text-slate-500"} icon={AlertTriangle} highlight={!!stats?.overdue} />
      </div>

      <h2 className="text-sm font-bold text-slate-800 mb-3">Inventory</h2>
      <CatalogueTab onIssue={(book) => setIssueTarget(book)} />
      {issueTarget && <IssueLoanDrawer book={issueTarget} onClose={() => setIssueTarget(null)} />}
    </div>
  );
}
