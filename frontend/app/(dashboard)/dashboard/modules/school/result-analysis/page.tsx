"use client";

import { Fragment, useMemo, useState } from "react";
import {
  useAnalysisClasses, usePerformanceTracker, useBoosterList, useHonoursRoll,
  useMyTeachingAssignments, useTerms, useSubTerms, useCurrentSession,
  useOrderOfMerit, useGradeSummary, useSubjectPerformance, useDepartmentalAnalysis,
  useAcrossSessions,
} from "@/hooks/usePlatform";
import { useHasPermission } from "@/components/guards/PermissionGate";
import { MeritTab, SummaryTab, SubjectsTab, DepartmentsTab, AcrossSessionsTab } from "@/components/reports/ResultAnalysisAdminTabs";
import { cn } from "@/lib/utils";
import { Download, Loader2, AlertCircle } from "lucide-react";

type Tab = "tracker" | "booster" | "honours" | "merit" | "summary" | "subjects"
  | "departments" | "across-sessions";

// The three a class teacher sees. An administrator sees these plus the
// whole-school reports below — one route, two views, resolved by permission.
const TEACHER_TABS: { key: Tab; label: string }[] = [
  { key: "tracker", label: "Performance Tracker" },
  { key: "booster", label: "Booster List" },
  { key: "honours", label: "Honours Roll" },
];
const ADMIN_TABS: { key: Tab; label: string }[] = [
  { key: "merit", label: "Order of Merit" },
  { key: "summary", label: "Grade Summary" },
  { key: "subjects", label: "Subject Performance" },
  { key: "departments", label: "Departmental Analysis" },
  { key: "across-sessions", label: "Averages Across Sessions" },
];

// An unmarked cell is not a zero. Everything that renders a score goes through
// this, including the export, so a blank can never become a 0 on the way out.
const DASH = "—";
const fmt = (v: unknown) => (v === null || v === undefined || v === "" ? DASH : String(v));

export default function ResultAnalysisPage() {
  const isAdmin = useHasPermission("school_admin:read");
  const [tab, setTab] = useState<Tab>("tracker");

  const { data: classes, isLoading: clsLoading, isError: clsError } = useAnalysisClasses();
  const { data: assignments } = useMyTeachingAssignments();
  const { data: terms } = useTerms();
  const { data: subTerms } = useSubTerms();
  const { data: session } = useCurrentSession();

  const classList = (classes ?? []) as Array<{ id: string; name: string }>;
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");

  // Only the subjects this teacher teaches IN THE SELECTED CLASS — the same
  // Timetable assignments Make Report gates mark entry on. The server checks this
  // too; a filtered dropdown is a convenience, not the control.
  const subjects = useMemo(() => {
    const rows = (assignments ?? []) as Array<{ class_id: string; subject_id: string; subject_name: string }>;
    const seen = new Set<string>();
    return rows
      .filter((a) => a.class_id === classId)
      .filter((a) => (seen.has(a.subject_id) ? false : (seen.add(a.subject_id), true)))
      .sort((a, b) => (a.subject_name || "").localeCompare(b.subject_name || ""));
  }, [assignments, classId]);

  // Booster and Honours are per CLASS and need a term + sub-term; the tracker
  // spans the whole session and does not.
  const termRows = (terms ?? []) as Array<{ id: string; name: string }>;
  const subRows = (subTerms ?? []) as Array<{ id: string; name: string }>;
  const [termId, setTermId] = useState("");
  const [subTermId, setSubTermId] = useState("");

  const tracker = usePerformanceTracker(classId, subjectId);
  const booster = useBoosterList(termId, subTermId, classId);
  const honours = useHonoursRoll(termId, subTermId, classId);
  // Whole-school when no class is chosen — these are an administrator's reports,
  // and class_id is optional on all three.
  const merit = useOrderOfMerit(termId, subTermId, classId || undefined);
  const summary = useGradeSummary(termId, subTermId, classId || undefined);
  // `subjectPerf`, not `subjects`: the latter is the teacher's own subject list
  // for the tracker dropdown, and shadowing it silently broke that dropdown.
  const subjectPerf = useSubjectPerformance(termId, subTermId, classId || undefined);
  const departments = useDepartmentalAnalysis(termId, subTermId, classId || undefined);
  // No termId: this report spans YEARS and folds each year's terms itself.
  const acrossSessions = useAcrossSessions(subTermId, classId || undefined);
  const visibleTabs = isAdmin ? [...TEACHER_TABS, ...ADMIN_TABS] : TEACHER_TABS;
  // These need a term and sub-term, like Booster and Honours; the tracker does
  // not, and Averages Across Sessions needs only the sub-term — it spans terms.
  const needsTerm = tab !== "tracker" && tab !== "across-sessions";

  const onClass = (v: string) => { setClassId(v); setSubjectId(""); };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Result Analysis</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          {isAdmin
            ? "Whole-school analysis, and any class's session performance."
            : "Your class's performance across the session."}
        </p>
      </div>

      {/* ── the filter form: nothing renders until it is filled ─────────────── */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Session</label>
            <input value={session?.name ?? ""} readOnly className="input bg-slate-50 text-slate-500"
                   placeholder="No current session" />
          </div>
          <div>
            <label className="label">Class *</label>
            <select value={classId} onChange={(e) => onClass(e.target.value)} className="input">
              <option value="">Select a class…</option>
              {classList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          {tab !== "tracker" && (
            <>
              {/* Averages Across Sessions has no term: it folds every term of
                  each year by itself. Showing a required-looking "Term *" that
                  the report ignores would be a control that does nothing. */}
              {tab !== "across-sessions" && (
                <div>
                  <label className="label">Term *</label>
                  <select value={termId} onChange={(e) => setTermId(e.target.value)} className="input">
                    <option value="">Select a term…</option>
                    {termRows.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="label">Sub-term *</label>
                <select value={subTermId} onChange={(e) => setSubTermId(e.target.value)} className="input">
                  <option value="">Select a sub-term…</option>
                  {subRows.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            </>
          )}
        </div>

        {/* A class list that came back EMPTY is not the same as one that failed,
            and neither is "you are not a class teacher". Say which. */}
        {clsError && (
          <p className="text-sm text-red-600 mt-3 flex items-center gap-2">
            <AlertCircle size={15} /> Could not load your classes. Reload, or ask an administrator.
          </p>
        )}
        {!clsLoading && !clsError && classList.length === 0 && (
          <p className="text-sm text-amber-700 mt-3">
            You are not the class teacher for any class, so there is no result analysis to show.
            Ask an administrator if you think this is wrong.
          </p>
        )}
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {visibleTabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={cn("px-4 py-2 text-sm font-medium -mb-px border-b-2",
              tab === t.key ? "border-emerald-600 text-emerald-700" : "border-transparent text-slate-500 hover:text-slate-700")}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "tracker" && (
        <TrackerTab classId={classId} subjectId={subjectId} setSubjectId={setSubjectId}
                    subjects={subjects} query={tracker} />
      )}
      {tab === "booster" && (
        <ThresholdTab title="Booster List" query={booster} classId={classId}
                      termId={termId} subTermId={subTermId} kind="booster" />
      )}
      {tab === "honours" && (
        <ThresholdTab title="Honours Roll" query={honours} classId={classId}
                      termId={termId} subTermId={subTermId} kind="honours" />
      )}
      {tab === "merit" && <MeritTab query={merit} termId={termId} subTermId={subTermId} />}
      {tab === "summary" && <SummaryTab query={summary} termId={termId} subTermId={subTermId} />}
      {tab === "subjects" && <SubjectsTab query={subjectPerf} termId={termId} subTermId={subTermId} />}
      {tab === "departments" && <DepartmentsTab query={departments} termId={termId} subTermId={subTermId} />}
      {tab === "across-sessions" && <AcrossSessionsTab query={acrossSessions} subTermId={subTermId} />}
    </div>
  );
}

// ── Performance Tracker ───────────────────────────────────────────────────────

function TrackerTab({ classId, subjectId, setSubjectId, subjects, query }: {
  classId: string; subjectId: string; setSubjectId: (v: string) => void;
  subjects: Array<{ subject_id: string; subject_name: string }>;
  query: { data: any; isLoading: boolean; isError: boolean; error?: any };
}) {
  const data = query.data;

  const exportExcel = () => {
    if (!data) return;
    // CSV with the SAME dashes the table shows. An export that turns a blank into
    // a 0 hands someone a spreadsheet asserting a mark that was never given, and
    // spreadsheets get forwarded far past the person who understood the gap.
    const head = ["SN", "Student Name",
      ...data.columns.flatMap((c: any) => [`${c.group ? c.group + " " : ""}${c.label} Score`,
                                           `${c.group ? c.group + " " : ""}${c.label} Grade`]),
      "Sessional Score", "Sessional Grade"];
    const rows = data.rows.map((r: any) => [
      r.sn, r.student_name,
      ...data.columns.flatMap((c: any) => [fmt(r.cells?.[c.key]?.score), fmt(r.cells?.[c.key]?.grade)]),
      fmt(r.sessional_score), fmt(r.sessional_grade),
    ]);
    const csv = [head, ...rows]
      .map((row) => row.map((v: any) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `performance-tracker-${data.class_name ?? "class"}-${data.subject_name ?? "subject"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-full sm:w-72">
          <label className="label">Subject *</label>
          <select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}
                  className="input" disabled={!classId}>
            <option value="">{classId ? "Select a subject…" : "Select a class first"}</option>
            {subjects.map((s) => (
              <option key={s.subject_id} value={s.subject_id}>{s.subject_name}</option>
            ))}
          </select>
          {classId && subjects.length === 0 && (
            <p className="text-[11px] text-amber-600 mt-1">
              You are not assigned to teach any subject in this class.
            </p>
          )}
        </div>
        <button onClick={exportExcel} disabled={!data || !data.rows?.length}
                className="btn-secondary gap-2">
          <Download size={15} /> Export Excel
        </button>
      </div>

      {!classId || !subjectId ? (
        <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
          <p className="font-semibold text-slate-600">Choose a class and a subject</p>
          <p className="text-sm text-slate-400 mt-1">
            The tracker is per subject — pick one above to see the class&apos;s results across the session.
          </p>
        </div>
      ) : query.isLoading ? (
        <div className="py-16 text-center text-slate-400">
          <Loader2 className="animate-spin mx-auto mb-2" size={20} /> Loading the session…
        </div>
      ) : query.isError ? (
        <div className="bg-white rounded-xl border border-red-200 py-12 text-center">
          <p className="font-semibold text-red-700">
            {query.error?.response?.data?.detail ?? "This tracker could not be loaded."}
          </p>
          <p className="text-sm text-slate-500 mt-1">
            This is a refusal, not an empty class — the two look alike and are not the same.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
            {data.class_name} · {data.subject_name}
            {data.session_name ? ` · ${data.session_name}` : ""}
            {data.not_configured && (
              <span className="ml-2 text-amber-700">
                — no term is set up for reporting yet, so every column is empty.
              </span>
            )}
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left font-medium">SN</th>
                <th className="px-3 py-2 text-left font-medium">Student Name</th>
                {data.columns.map((c: any) => (
                  <th key={c.key} colSpan={2}
                      className={cn("px-3 py-2 text-center font-medium border-l border-slate-200",
                                    !c.available && "text-slate-300")}>
                    {c.group ? <span className="block text-[10px] uppercase">{c.group}</span> : null}
                    {c.label}
                  </th>
                ))}
                <th colSpan={2} className="px-3 py-2 text-center font-medium border-l border-slate-200">
                  Sessional Score
                </th>
              </tr>
              <tr className="text-[11px]">
                <th /><th />
                {data.columns.map((c: any) => (
                  <Fragment key={c.key}>
                    {/* Every tracker value is a percentage — subject_pct is
                        value/max*100 — which is what makes Autumn and Spring
                        comparable side by side. The unit was missing from the
                        header, so a capped figure elsewhere could be read into
                        these. */}
                    <th className="px-2 py-1 font-normal border-l border-slate-200">Score %</th>
                    <th className="px-2 py-1 font-normal">Grade</th>
                  </Fragment>
                ))}
                <th className="px-2 py-1 font-normal border-l border-slate-200">Score %</th>
                <th className="px-2 py-1 font-normal">Grade</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.rows.map((r: any) => (
                <tr key={r.student_id} className="hover:bg-slate-50">
                  <td className="px-3 py-2 text-slate-400">{r.sn}</td>
                  <td className="px-3 py-2 font-medium text-slate-800">{r.student_name}</td>
                  {data.columns.map((c: any) => (
                    <Fragment key={c.key}>
                      <td className="px-2 py-2 text-center border-l border-slate-100">
                        {fmt(r.cells?.[c.key]?.score)}
                      </td>
                      <td className="px-2 py-2 text-center">
                        {fmt(r.cells?.[c.key]?.grade)}
                      </td>
                    </Fragment>
                  ))}
                  <td className="px-2 py-2 text-center border-l border-slate-100 font-medium">
                    {fmt(r.sessional_score)}
                  </td>
                  <td className="px-2 py-2 text-center">{fmt(r.sessional_grade)}</td>
                </tr>
              ))}
              {!data.rows.length && (
                <tr><td colSpan={99} className="px-5 py-12 text-center text-slate-400">
                  No pupils in this class.
                </td></tr>
              )}
            </tbody>
          </table>
          <p className="px-5 py-3 text-[11px] text-slate-400 border-t border-slate-100">
            {DASH} means no mark has been entered — it is not a zero. A column greyed in the header
            has no cumulative configured for that sub-term yet.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Booster List / Honours Roll: per class, from the Wave 1 endpoints ─────────

function ThresholdTab({ title, query, classId, termId, subTermId, kind }: {
  title: string; query: { data: any; isLoading: boolean; isError: boolean; error?: any };
  classId: string; termId: string; subTermId: string; kind: "booster" | "honours";
}) {
  const data = query.data;
  if (!classId || !termId || !subTermId) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 py-16 text-center">
        <p className="font-semibold text-slate-600">Choose a class, term and sub-term</p>
        <p className="text-sm text-slate-400 mt-1">{title} is per class for one sub-term.</p>
      </div>
    );
  }
  if (query.isLoading) {
    return <div className="py-16 text-center text-slate-400">
      <Loader2 className="animate-spin mx-auto mb-2" size={20} /> Loading…
    </div>;
  }
  if (query.isError) {
    return (
      <div className="bg-white rounded-xl border border-red-200 py-12 text-center">
        <p className="font-semibold text-red-700">
          {query.error?.response?.data?.detail ?? `${title} could not be loaded.`}
        </p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
      <div className="px-5 py-3 border-b border-slate-100 text-sm text-slate-500">
        {data.class_name} · {data.term_name} {data.sub_term_name} · threshold{" "}
        <span className="font-medium text-slate-700">{fmt(data.threshold)}</span>
        {data.threshold_source !== "configured" && (
          <span className="ml-2 text-amber-700">
            (threshold is {data.threshold_source} — nobody has set one, so treat this as provisional)
          </span>
        )}
        <span className="ml-2">· {data.considered} assessed</span>
        {data.unmarked > 0 && (
          <span className="ml-2 text-slate-400">· {data.unmarked} with no marks, listed in neither</span>
        )}
      </div>
      {data.not_configured ? (
        <p className="px-5 py-12 text-center text-amber-700">
          This term has no cumulative or assessments set up, so nothing can be computed.
          That is different from nobody qualifying.
        </p>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left font-medium">#</th>
              <th className="px-4 py-2 text-left font-medium">Student</th>
              <th className="px-4 py-2 text-left font-medium">Average</th>
              <th className="px-4 py-2 text-left font-medium">Grade</th>
              <th className="px-4 py-2 text-left font-medium">
                {kind === "booster" ? "Subjects below the pass mark" : "Subjects counted"}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.pupils.map((p: any, i: number) => (
              <tr key={p.student_id} className="hover:bg-slate-50">
                <td className="px-4 py-2 text-slate-400">{p.position ?? i + 1}</td>
                <td className="px-4 py-2 font-medium text-slate-800">{p.student_name}</td>
                <td className="px-4 py-2">{fmt(p.average)}</td>
                <td className="px-4 py-2">{fmt(p.grade)}</td>
                <td className="px-4 py-2 text-slate-600">
                  {kind === "booster"
                    ? (p.subjects_below?.length
                        ? p.subjects_below.map((s: any) => `${s.subject_name} (${s.percentage})`).join(", ")
                        : DASH)
                    : p.subjects_counted}
                </td>
              </tr>
            ))}
            {!data.pupils.length && (
              <tr><td colSpan={5} className="px-5 py-12 text-center text-slate-400">
                {kind === "booster"
                  ? "No pupil is below the pass mark for this sub-term."
                  : "No pupil has reached the honours threshold for this sub-term."}
              </td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
