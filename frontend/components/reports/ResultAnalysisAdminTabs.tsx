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

export function DepartmentsTab({ query, termId, subTermId }: {
  query: Query; termId: string; subTermId: string;
}) {
  return (
    <ReportShell query={query} termId={termId} subTermId={subTermId}
                 title="Departmental Analysis">
      {(d) => (
        <>
          {d.no_departments && (
            <p className="px-5 py-3 text-sm text-amber-700 border-b border-amber-100 bg-amber-50">
              No subject has a department yet, so everything falls under “Unassigned”.
              Set departments on the Subjects page to break this down.
            </p>
          )}
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Department</th>
                <th className="px-3 py-2 text-center font-medium">Marks</th>
                <th className="px-3 py-2 text-center font-medium">Pupils</th>
                <th className="px-3 py-2 text-center font-medium">Average %</th>
                <th className="px-3 py-2 text-center font-medium">Highest</th>
                <th className="px-3 py-2 text-center font-medium">Lowest</th>
                <th className="px-3 py-2 text-center font-medium">Pass rate</th>
                <th className="px-3 py-2 text-center font-medium">Incomplete</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {d.rows.map((r: any) => (
                <tr key={r.department ?? "__unassigned__"} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    {/* An unassigned row is a gap to close, not a peer of the real
                        departments — named as such and visibly set apart. */}
                    <span className={cn("font-medium",
                                        r.department ? "text-slate-800" : "text-amber-700")}>
                      {r.department ?? "Unassigned"}
                    </span>
                    <span className="block text-[11px] text-slate-400">
                      {r.subjects.join(", ")}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-center tabular-nums text-slate-500">{r.entered}</td>
                  <td className="px-3 py-2 text-center tabular-nums text-slate-500">{r.pupils}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.average)}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.highest)}</td>
                  <td className="px-3 py-2 text-center tabular-nums">{fmt(r.lowest)}</td>
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
            . “Incomplete” pupil-subjects have some marks but not every component the total
            needs, and are counted in no other column here.
          </p>
        </>
      )}
    </ReportShell>
  );
}

/**
 * Subjects Averages Across Sessions — the report migration 134 existed for.
 *
 * It has its OWN shell rather than reusing ReportShell: that one guards on a
 * term and labels its empty state "Choose a term and sub-term", and this report
 * deliberately has no term. It spans years and folds each year's terms. Reusing
 * it would have meant either a misleading prompt or a fake term id.
 *
 * The states it must keep apart are the same ones, though, so they are handled
 * the same way — a refusal is never allowed to render as an empty grid.
 */
export function AcrossSessionsTab({ query, subTermId }: {
  query: Query; subTermId: string;
}) {
  if (!subTermId) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
        <p className="font-semibold text-slate-600">Choose a sub-term</p>
        <p className="text-sm text-slate-400 mt-1">
          One sub-term is compared across every academic year, so a Mock is never
          averaged against a Full-Term.
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
          {query.error?.response?.data?.detail ?? "Averages across sessions could not be loaded."}
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
        <p className="font-semibold text-amber-700">
          No academic year is set up for this sub-term.
        </p>
        <p className="text-sm text-slate-500 mt-1">
          Nothing can be computed for it in any year — different from a year that
          is set up and unmarked.
        </p>
      </div>
    );
  }

  const cols = d.columns ?? [];
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
        {d.class_name ? `${d.class_name} · ` : "Whole school · "}
        {d.sub_term_name} · across {cols.length} academic year{cols.length === 1 ? "" : "s"}
      </div>

      {/* One year of figures is not a comparison. Said plainly, so a grid with a
          single populated column reads as "too early" and not as broken. */}
      {d.single_session && (
        <p className="px-5 py-3 text-sm text-sky-800 border-b border-sky-100 bg-sky-50">
          Only one academic year holds results so far, so there is no trend to show
          yet. The comparison fills in once a second year has been marked.
        </p>
      )}

      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Subject</th>
            <th className="px-3 py-2 text-left font-medium">Department</th>
            {cols.map((c: any) => (
              <th key={c.session_id} className="px-3 py-2 text-center font-medium whitespace-nowrap">
                {c.session_name}
                {c.is_current && <span className="ml-1 text-emerald-600">•</span>}
                <span className="block text-[11px] font-normal text-slate-400">
                  {c.not_configured
                    ? "not set up"
                    : `${c.terms_counted} term${c.terms_counted === 1 ? "" : "s"}`}
                </span>
              </th>
            ))}
            <th className="px-3 py-2 text-center font-medium">Overall</th>
            <th className="px-3 py-2 text-center font-medium">Trend</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {d.rows.map((r: any) => (
            <tr key={r.subject_id} className="hover:bg-slate-50">
              <td className="px-4 py-2 font-medium text-slate-800">{r.subject_name}</td>
              <td className="px-3 py-2 text-slate-500">
                {r.department ?? <span className="text-slate-400">Unassigned</span>}
              </td>
              {cols.map((c: any) => {
                const cell = r.cells?.[c.session_id];
                return (
                  <td key={c.session_id} className="px-3 py-2 text-center">
                    {cell && cell.average !== null && cell.average !== undefined ? (
                      <>
                        {fmt(cell.average)}
                        {/* A figure resting on one term of a multi-term year is
                            flagged: it is a partial year, not the year. */}
                        {cell.terms_counted === 1 && c.terms_counted > 1 && (
                          <span className="block text-[11px] text-amber-600">1 term</span>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-300" title="Not entered">{DASH}</span>
                    )}
                  </td>
                );
              })}
              <td className="px-3 py-2 text-center font-semibold">{fmt(r.overall)}</td>
              <td className="px-3 py-2 text-center">
                {r.trend === null || r.trend === undefined ? (
                  <span className="text-slate-300" title="Needs two marked years">{DASH}</span>
                ) : (
                  <span className={cn("font-semibold",
                    Number(r.trend) > 0 ? "text-emerald-700"
                      : Number(r.trend) < 0 ? "text-red-700" : "text-slate-500")}>
                    {Number(r.trend) > 0 ? "+" : ""}{fmt(r.trend)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


/**
 * Averages Across Terms — the sibling of AcrossSessionsTab, one level down:
 * that compares years, this compares the terms inside one.
 *
 * Its own guard rather than ReportShell's, for the same reason: it has no term
 * of its own, and ReportShell prompts for one.
 */
export function AcrossTermsTab({ query, subTermId }: {
  query: Query; subTermId: string;
}) {
  if (!subTermId) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
        <p className="font-semibold text-slate-600">Choose a sub-term</p>
        <p className="text-sm text-slate-400 mt-1">
          One sub-term is compared across every term of the session, so a Mock is
          never averaged against a Full-Term.
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
          {query.error?.response?.data?.detail ?? "Averages across terms could not be loaded."}
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
        <p className="font-semibold text-amber-700">
          No term is set up for this sub-term.
        </p>
        <p className="text-sm text-slate-500 mt-1">
          Nothing can be computed for it — different from a term that is set up
          and unmarked.
        </p>
      </div>
    );
  }

  const cols = d.columns ?? [];
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
        {d.class_name ? `${d.class_name} · ` : "Whole school · "}
        {d.sub_term_name} · across {cols.length} term{cols.length === 1 ? "" : "s"}
      </div>

      {d.single_term && (
        <p className="px-5 py-3 text-sm text-sky-800 border-b border-sky-100 bg-sky-50">
          Only one term holds results so far, so there is no trend to show yet.
        </p>
      )}

      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="px-4 py-2 text-left font-medium">Subject</th>
            <th className="px-3 py-2 text-left font-medium">Department</th>
            {cols.map((c: any) => (
              <th key={c.term_id} className="px-3 py-2 text-center font-medium whitespace-nowrap">
                {c.term_name}
                <span className="block text-[11px] font-normal text-slate-400">
                  {!c.configured ? "not set up"
                    : c.pupils_marked ? `${c.pupils_marked} marked` : "no marks"}
                </span>
              </th>
            ))}
            <th className="px-3 py-2 text-center font-medium">Overall</th>
            <th className="px-3 py-2 text-center font-medium">Trend</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {d.rows.map((r: any) => (
            <tr key={r.subject_id} className="hover:bg-slate-50">
              <td className="px-4 py-2 font-medium text-slate-800">{r.subject_name}</td>
              <td className="px-3 py-2 text-slate-500">
                {r.department ?? <span className="text-slate-400">Unassigned</span>}
              </td>
              {cols.map((c: any) => {
                const cell = r.cells?.[c.term_id];
                return (
                  <td key={c.term_id} className="px-3 py-2 text-center">
                    {cell && cell.average != null
                      ? fmt(cell.average)
                      : <span className="text-slate-300" title="Not entered">{DASH}</span>}
                  </td>
                );
              })}
              <td className="px-3 py-2 text-center font-semibold">{fmt(r.overall)}</td>
              <td className="px-3 py-2 text-center">
                {r.trend == null ? (
                  <span className="text-slate-300" title="Needs two marked terms">{DASH}</span>
                ) : (
                  <span className={cn("font-semibold",
                    Number(r.trend) > 0 ? "text-emerald-700"
                      : Number(r.trend) < 0 ? "text-red-700" : "text-slate-500")}>
                    {Number(r.trend) > 0 ? "+" : ""}{fmt(r.trend)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const REASON_LABEL: Record<string, string> = {
  fell_below_pass: "Fell below pass mark",
  steep_drop: "Steep drop",
  incomplete: "Incomplete marks",
};
const REASON_STYLE: Record<string, string> = {
  fell_below_pass: "bg-red-50 text-red-700 border-red-200",
  steep_drop: "bg-amber-50 text-amber-700 border-amber-200",
  incomplete: "bg-slate-50 text-slate-600 border-slate-200",
};

/**
 * Academic Alert — pupils needing attention, with the reason for each.
 *
 * The empty state is the interesting one. An empty list on its own reads as
 * broken, so the counts and the denominator are always shown: "0 flagged of 180
 * considered, threshold 5" is a result.
 */
export function AlertTab({ query, subTermId, threshold, setThreshold }: {
  query: Query; subTermId: string;
  threshold: number; setThreshold: (v: number) => void;
}) {
  const picker = (
    <div className="flex items-end gap-2">
      <div>
        <label className="label">Steep drop (points)</label>
        <input type="number" min={0} step={0.5} value={threshold}
               onChange={(e) => setThreshold(Number(e.target.value))}
               className="input w-28" />
      </div>
    </div>
  );

  if (!subTermId) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
        <p className="font-semibold text-slate-600">Choose a sub-term</p>
        <p className="text-sm text-slate-400 mt-1">
          Movement is compared between the terms of the session for one sub-term.
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
          {query.error?.response?.data?.detail ?? "The academic alert could not be loaded."}
        </p>
        <p className="text-sm text-slate-500 mt-1">A refusal, not an empty result.</p>
      </div>
    );
  }
  const d = query.data;
  if (!d) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        {picker}
        <p className="text-xs text-slate-400 max-w-md">
          A pupil is flagged for every reason that applies. Falling below the pass
          mark and dropping steeply are two different conversations.
        </p>
      </div>

      {d.not_configured ? (
        <div className="bg-white rounded-xl border border-amber-200 py-12 text-center">
          <p className="font-semibold text-amber-700">No term is set up for this sub-term.</p>
          <p className="text-sm text-slate-500 mt-1">
            Nothing can be computed — different from nobody being at risk.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
            {d.class_name ? `${d.class_name} · ` : "Whole school · "}
            {d.sub_term_name}
            {d.first_term_name && d.last_term_name
              ? ` · ${d.first_term_name} → ${d.last_term_name}`
              : ""}
            {" · pass mark "}{fmt(d.passmark)}
          </div>

          {/* Always shown, flagged or not: the denominator is what makes an
              empty list a result rather than a malfunction. */}
          <p className="px-5 py-2 text-xs text-slate-500 border-b border-slate-100 bg-slate-50/60">
            {d.rows.length} flagged of {d.considered} pupil{d.considered === 1 ? "" : "s"} with
            an average in both terms · drop ≥ {fmt(d.drop_threshold)} ·{" "}
            {Object.entries(REASON_LABEL).map(([k, label], i) => (
              <span key={k}>{i > 0 ? " · " : ""}{label}: {d.counts?.[k] ?? 0}</span>
            ))}
            {d.single_term && " · only one term is marked, so no movement can be computed"}
          </p>

          {d.rows.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">
              Nobody meets any alert condition at this threshold.
              {d.considered > 0 && <> Lower the drop threshold to widen the net.</>}
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Pupil</th>
                  <th className="px-3 py-2 text-left font-medium">Class</th>
                  <th className="px-3 py-2 text-center font-medium">{d.first_term_name ?? "First"}</th>
                  <th className="px-3 py-2 text-center font-medium">{d.last_term_name ?? "Last"}</th>
                  <th className="px-3 py-2 text-center font-medium">Change</th>
                  <th className="px-4 py-2 text-left font-medium">Why</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {d.rows.map((r: any) => (
                  <tr key={r.student_id} className="hover:bg-slate-50">
                    <td className="px-4 py-2">
                      <p className="font-medium text-slate-800">{r.student_name}</p>
                      {r.admission_no && (
                        <p className="text-[11px] text-slate-400">{r.admission_no}</p>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-500">{fmt(r.class_name)}</td>
                    <td className="px-3 py-2 text-center">{fmt(r.first_average)}</td>
                    <td className="px-3 py-2 text-center">{fmt(r.last_average)}</td>
                    <td className="px-3 py-2 text-center">
                      {r.change == null ? (
                        <span className="text-slate-300" title="No movement to compute">{DASH}</span>
                      ) : (
                        <span className="font-semibold text-red-700">{fmt(r.change)}</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.reasons.map((k: string) => (
                          <span key={k} className={cn("badge", REASON_STYLE[k] ?? REASON_STYLE.incomplete)}>
                            {REASON_LABEL[k] ?? k}
                          </span>
                        ))}
                      </div>
                      {r.incomplete_subjects?.length > 0 && (
                        <p className="text-[11px] text-slate-400 mt-1">
                          Unmarked components in: {r.incomplete_subjects.join(", ")}
                        </p>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
