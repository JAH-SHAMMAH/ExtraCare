"use client";

import { BookOpen, Clock, AlertTriangle, CheckCircle2, Calendar } from "lucide-react";
import { useMyLoans, type LibraryLoanRow } from "@/hooks/useSchool";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { Skeleton } from "@/components/loading/Skeleton";
import { cn, formatDate } from "@/lib/utils";

/**
 * Student "My Library" — active loans on top (with due-in countdown), then a
 * collapsed history below. Uses /library/loans/mine for a single round-trip.
 */
export default function MyLibraryPage() {
  const { data, isLoading } = useMyLoans();
  const showSkeleton = useDelayedFlag(isLoading);

  const active = data?.active ?? [];
  const history = data?.history ?? [];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Student</span><span>/</span>
          <span className="text-brand-600 font-semibold">My Library</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">My Library</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Books you&apos;ve borrowed and their due dates.
        </p>
      </div>

      {showSkeleton ? (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      ) : (
        <>
          {/* Active loans */}
          <section className="mb-8">
            <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
              <Clock size={14} /> Currently borrowed ({active.length})
            </h2>
            {active.length === 0 ? (
              <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
                <BookOpen size={28} className="text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">No books checked out</p>
                <p className="text-xs text-slate-500 mt-1">Visit the library to borrow your first book.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {active.map((l) => <ActiveLoanCard key={l.id} loan={l} />)}
              </div>
            )}
          </section>

          {/* History */}
          {history.length > 0 && (
            <section>
              <h2 className="text-sm font-bold text-slate-800 mb-3 flex items-center gap-2">
                <CheckCircle2 size={14} /> Recently returned
              </h2>
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
                {history.map((l) => (
                  <div key={l.id} className="flex items-center gap-3 px-5 py-3 text-sm">
                    <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
                      <BookOpen size={13} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-slate-800 truncate">{l.book_title}</p>
                      <p className="text-xs text-slate-500 truncate">{l.book_author}</p>
                    </div>
                    <span className="text-xs text-slate-400 shrink-0">
                      Returned {l.returned_at ? formatDate(l.returned_at) : "—"}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ActiveLoanCard({ loan }: { loan: LibraryLoanRow }) {
  const daysUntilDue = daysBetween(new Date(), new Date(loan.due_date));
  const isOverdue = loan.is_overdue;
  const isDueSoon = !isOverdue && daysUntilDue <= 3;

  const accent = isOverdue
    ? "bg-rose-50 border-rose-200 text-rose-800"
    : isDueSoon
    ? "bg-amber-50 border-amber-200 text-amber-800"
    : "bg-emerald-50 border-emerald-200 text-emerald-800";

  const badgeLabel = isOverdue
    ? `${Math.abs(daysUntilDue)} day${Math.abs(daysUntilDue) === 1 ? "" : "s"} overdue`
    : daysUntilDue === 0
    ? "Due today"
    : daysUntilDue === 1
    ? "Due tomorrow"
    : `${daysUntilDue} days left`;

  return (
    <div className={cn(
      "bg-white rounded-xl border overflow-hidden",
      isOverdue ? "border-rose-300 ring-2 ring-rose-100" : "border-slate-200",
    )}>
      <div className="p-5">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-brand-50 to-indigo-50 text-brand-700 flex items-center justify-center shrink-0">
            <BookOpen size={18} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-slate-900 line-clamp-2">{loan.book_title}</p>
            <p className="text-xs text-slate-500 truncate">{loan.book_author}</p>
            {loan.book_category && (
              <span className="badge bg-slate-50 text-slate-600 border-slate-200 text-[9px] mt-1.5">
                {loan.book_category}
              </span>
            )}
          </div>
        </div>
        <div className={cn("rounded-lg border px-3 py-2 flex items-center gap-2", accent)}>
          {isOverdue
            ? <AlertTriangle size={14} />
            : isDueSoon
            ? <Clock size={14} />
            : <Calendar size={14} />}
          <div className="flex-1">
            <p className="text-[10px] font-bold uppercase tracking-widest opacity-80">
              Due {loan.due_date}
            </p>
            <p className="text-sm font-bold">{badgeLabel}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function daysBetween(a: Date, b: Date): number {
  const msPerDay = 1000 * 60 * 60 * 24;
  const d1 = new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  const d2 = new Date(b.getFullYear(), b.getMonth(), b.getDate()).getTime();
  return Math.round((d2 - d1) / msPerDay);
}
