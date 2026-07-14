"use client";

import { useMemo } from "react";
import { Users2, Loader2, BookOpen } from "lucide-react";
import { useLibraryLoans, type LibraryLoanRow } from "@/hooks/useSchool";
import { cn } from "@/lib/utils";

/**
 * Library — User Dashboard. Borrowing activity per member, derived from the loan
 * register: who currently holds books, how many, and who's overdue.
 */
export default function LibraryUsersPage() {
  const { data, isLoading } = useLibraryLoans({ page_size: 100 });
  const loans = data?.items ?? [];

  const borrowers = useMemo(() => {
    const map = new Map<string, { name: string; email: string | null; active: number; overdue: number; total: number }>();
    for (const l of loans as LibraryLoanRow[]) {
      const key = l.borrower_user_id;
      const row = map.get(key) ?? { name: l.borrower_name || "—", email: l.borrower_email, active: 0, overdue: 0, total: 0 };
      row.total += 1;
      if (l.status === "borrowed") row.active += 1;
      if (l.is_overdue) row.overdue += 1;
      map.set(key, row);
    }
    return Array.from(map.values()).sort((a, b) => b.active - a.active || b.total - a.total);
  }, [loans]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2"><span>Education</span><span>/</span><span>Library</span><span>/</span><span className="text-brand-600 font-semibold">User Dashboard</span></nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2"><Users2 size={22} className="text-brand-600" /> User Dashboard</h1>
        <p className="text-slate-500 text-sm mt-0.5">Borrowing activity by member.</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead><tr className="bg-slate-50/80 border-b border-slate-100">{["Member", "Currently holding", "Overdue", "Total borrowed"].map((h) => <th key={h} className="px-5 py-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">{h}</th>)}</tr></thead>
          <tbody className="divide-y divide-slate-50">
            {isLoading ? <tr><td colSpan={4} className="px-5 py-10 text-center"><Loader2 className="animate-spin mx-auto text-slate-400" /></td></tr>
              : borrowers.length === 0 ? <tr><td colSpan={4} className="px-5 py-12 text-center text-sm text-slate-400"><BookOpen size={26} className="mx-auto mb-2 opacity-40" />No borrowing activity yet.</td></tr>
                : borrowers.map((b, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-5 py-3.5"><p className="text-sm font-semibold text-slate-800">{b.name}</p>{b.email && <p className="text-xs text-slate-400">{b.email}</p>}</td>
                    <td className="px-5 py-3.5 text-sm tabular-nums text-slate-700">{b.active}</td>
                    <td className="px-5 py-3.5"><span className={cn("text-sm tabular-nums font-semibold", b.overdue ? "text-rose-600" : "text-slate-400")}>{b.overdue}</span></td>
                    <td className="px-5 py-3.5 text-sm tabular-nums text-slate-500">{b.total}</td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
