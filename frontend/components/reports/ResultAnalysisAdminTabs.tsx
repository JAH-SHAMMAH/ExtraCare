"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

// An unmarked figure is not a zero. Everything that renders a number here goes
// through `fmt`, matching the teacher tabs.
const DASH = "—";
const fmt = (v: unknown) => (v === null || v === undefined || v === "" ? DASH : String(v));

type Query = { data: any; isLoading: boolean; isError: boolean; error?: any };

/**
 * One shell for all three whole-school reports, so the states that matter —
 * loading, refused, and "the term was never set up" — are handled identically
 * and cannot drift into each other. A refusal rendering as an empty table is the
 * failure this shell exists to prevent; it has happened on other pages here.
 */
function ReportShell({ query, termId, subTermId, title, children }: {
  query: Query; termId: string; subTermId: string; title: string;
  children: (data: any) => React.ReactNode;
}) {
  if (!termId || !subTermId) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
        <p className="font-semibold text-slate-600">Choose a term and sub-term</p>
        <p className="text-sm text-slate-400 mt-1">
          {title} covers the whole school unless you also pick a class.
        </p>
      </div>
    );
  }
  if (query.isLoading) {
    return (
      <div className="py-16 text-center text-slate-400">
        <Loader2 className="animate-spin mx-auto mb-2" size={20} /> Loading…
      </div>
    );
  }
  if (query.isError) {
    return (
      <div className="bg-white rounded-xl border border-red-200 py-12 text-center">
        <p className="font-semibold text-red-700">
          {query.error?.response?.data?.detail ?? `${title} could not be loaded.`}
        </p>
        <p className="text-sm text-slate-500 mt-1">A refusal, not an empty result.</p>
      </div>
    );
  }
  const d = query.data;
  if (!d) return null;
  if (d.not_configured) {
    return (
      <div className="bg-white rounded-xl border border-amber-200 py-12 text-center">
        <p className="font-semibold text-amber-700">This term is not set up for reporting.</p>
        <p className="text-sm text-slate-500 mt-1">
          It has no cumulative or assessments, so nothing can be computed. That is
          different from nobody qualifying.
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
        {d.class_name ? `${d.class_name} · ` : "Whole school · "}
        {d.term_name} {d.sub_term_name}
      </div>
      {children(d)}
    </div>
  );
}

export function MeritTab({ query, termId, subTermId }: {
  query: Query; termId: string; subTermId: string;
}) {
  return (
    <ReportShell query={query} termId={termId} subTermId={subTermId} title="Order of Merit">
      {(d) => (
        <>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Pos</th>
                <th className="px-4 py-2 text-left font-medium">Student</th>
                <th className="px-4 py-2 text-left font-medium">Class</th>
                <th className="px-4 py-2 text-left font-medium">Average %</th>
                <th className="px-4 py-2 text-left font-medium">Grade</th>
                <th className="px-4 py-2 text-left font-medium">Subjects</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.rows.map((r: any) => (
                <tr key={r.student_id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 text-slate-500 tabular-nums">
                    {r.position}
                    {r.tied && (
                      <span className="text-slate-400" title="shares this position">=</span>
                    )}
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-800">{r.student_name}</td>
                  <td className="px-4 py-2 text-slate-500">{fmt(r.class_name)}</td>
                  <td className="px-4 py-2 tabular-nums">{fmt(r.average)}</td>
                  <td className="px-4 py-2">{fmt(r.grade)}</td>
                  <td className="px-4 py-2 text-slate-500">{r.subjects_counted}</td>
                </tr>
              ))}
              {!d.rows.length && (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-slate-400">
                    No pupil has a complete set of marks for this sub-term.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="px-5 py-3 text-[11px] text-slate-400 border-t border-slate-100">
            {d.considered} ranked
            {d.unmarked ? `, ${d.unmarked} not ranked (no marks entered)` : ""}. Equal
            averages share a position, and the next place skips accordingly.
          </p>
        </>
      )}
    </ReportShell>
  );
}

export function SummaryTab({ query, termId, subTermId }: {
  query: Query; termId: string; subTermId: string;
}) {
  return (
    <ReportShell query={query} termId={termId} subTermId={subTermId} title="Grade Summary">
      {(d) => (
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Subject</th>
              {d.grades.map((g: string) => (
                <th key={g} className="px-3 py-2 text-center font-medium">{g}</th>
              ))}
              <th className="px-3 py-2 text-center font-medium">Entered</th>
              <th className="px-3 py-2 text-center font-medium">Average %</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {d.rows.map((r: any) => (
              <tr key={r.subject_id} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-medium text-slate-800">{r.subject_name}</td>
                {d.grades.map((g: string) => (
                  <td key={g} className="px-3 py-2 text-center tabular-nums">
                    {r.counts?.[g] ?? 0}
                  </td>
                ))}
                <td className="px-3 py-2 text-center tabular-nums text-slate-500">{r.entered}</td>
                <td className="px-3 py-2 text-center tabular-nums">{fmt(r.average)}</td>
              </tr>
            ))}
            {d.total_row && (
              <tr className="bg-slate-50 font-semibold">
                <td className="px-4 py-2">{d.total_row.subject_name}</td>
                {d.grades.map((g: string) => (
                  <td key={g} className="px-3 py-2 text-center tabular-nums">
                    {d.total_row.counts?.[g] ?? 0}
                  </td>
                ))}
                <td className="px-3 py-2 text-center tabular-nums">{d.total_row.entered}</td>
                <td className="px-3 py-2 text-center tabular-nums">{fmt(d.total_row.average)}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </ReportShell>
  );
}

export function SubjectsTab({ query, termId, subTermId }: {
  query: Query; termId: string; subTermId: string;
}) {
  return (
    <ReportShell query={query} termId={termId} subTermId={subTermId} title="Subject Performance">
      {(d) => (
        <>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Subject</th>
                <th className="px-3 py-2 text-center font-medium">Entered</th>
                <th className="px-3 py-2 text-center font-medium">Average %</th>
                <th className="px-3 py-2 text-center font-medium">Highest</th>
                <th className="px-3 py-2 text-center font-medium">Lowest</th>
                <th className="px-3 py-2 text-center font-medium">Passed</th>
                <th className="px-3 py-2 text-center font-medium">Pass rate</th>
                <th className="px-3 py-2 text-center font-medium">Incomplete</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.rows.map((r: any) => (
                <tr key={r.subject_id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 font-medium text-slate-800">{r.subject_name}</td>
                  <td className="px-3 py-2 text-center tabular-nums text-slate-500">{r.entered}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.average)}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.highest)}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.lowest)}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{r.passed}</td>
                  <td className="px-3 py-2 text-center tabular-nums">
                    {r.pass_rate == null ? DASH : `${r.pass_rate}%`}
                  </td>
                  <td className={cn("px-3 py-2 text-center tabular-nums",
                                    r.incomplete ? "text-amber-700" : "text-slate-400")}>
                    {r.incomplete}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-5 py-3 text-[11px] text-slate-400 border-t border-slate-100">
            Pass mark {fmt(d.passmark)}
            {d.threshold_source !== "configured" &&
              ` — ${d.threshold_source}; nobody has set one, so treat these rates as provisional`}
            . “Incomplete” pupils have some marks but not every component the total needs,
            and are counted in no other column here.
          </p>
        </>
      )}
    </ReportShell>
  );
}
