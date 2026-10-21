"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { cbtApi } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import {
  MonitorCheck, Clock, Award, Loader2, Dumbbell, TrendingUp, FileText, FlaskConical, ClipboardList,
  CheckCircle2, BookOpenCheck,
} from "lucide-react";
import type { CBTExam } from "@/types";

/**
 * Student exam portal. Tabs: school Exams, Tests and Mock exams (scheduled by
 * teachers), self-service Practice, and My Progress. Everything is scoped to the
 * signed-in student server-side.
 */

type Tab = "exam" | "test" | "mock" | "practice" | "progress";
const TABS: { key: Tab; label: string; icon: typeof FileText }[] = [
  { key: "exam", label: "Exams", icon: FileText },
  { key: "test", label: "Tests", icon: ClipboardList },
  { key: "mock", label: "Mock", icon: FlaskConical },
  { key: "practice", label: "Practice", icon: Dumbbell },
  { key: "progress", label: "My Progress", icon: TrendingUp },
];

export default function MyExamsPage() {
  return (
    <Suspense fallback={<div className="p-8"><Loader2 className="animate-spin text-brand-600" /></div>}>
      <Portal />
    </Suspense>
  );
}

function Portal() {
  const router = useRouter();
  const sp = useSearchParams();
  const initial = (TABS.find((t) => t.key === sp.get("tab"))?.key ?? "exam") as Tab;
  const [tab, setTab] = useState<Tab>(initial);
  const go = (t: Tab) => { setTab(t); router.replace(`/dashboard/my-exams?tab=${t}`, { scroll: false }); };

  return (
    <div className="p-4 sm:p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span><span>/</span><span className="text-brand-600 font-semibold">Exam Portal</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Exam Portal</h1>
        <p className="text-slate-500 text-sm mt-0.5">Sit your school exams, tests and mocks, practise on your own, and watch your progress.</p>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-slate-200 mb-6" role="tablist">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} role="tab" aria-selected={tab === key} onClick={() => go(key)}
            className={cn("flex items-center gap-2 px-4 py-2.5 text-sm font-semibold whitespace-nowrap border-b-2 -mb-px transition",
              tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800")}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {tab === "practice" ? <PracticeTab /> : tab === "progress" ? <ProgressTab /> : <ScheduledTab kind={tab} />}
    </div>
  );
}

// ── Exams / Tests / Mock ──────────────────────────────────────────────────────

const KIND_COPY: Record<string, { empty: string; sub: string }> = {
  exam: { empty: "No exams yet", sub: "School exams appear here when your teacher posts them." },
  test: { empty: "No tests yet", sub: "Class tests appear here when your teacher posts them." },
  mock: { empty: "No mock exams yet", sub: "Mock exams appear here when your school schedules them." },
};

function ScheduledTab({ kind }: { kind: "exam" | "test" | "mock" }) {
  const { data, isLoading } = useQuery({
    queryKey: ["my-exams", kind],
    queryFn: () => cbtApi.exams.list({ for_me: true, exam_type: kind, page: 1, page_size: 100 }),
  });
  const { data: att } = useQuery({ queryKey: ["my-attempts"], queryFn: () => cbtApi.attempts.list() });
  const exams = (data?.items ?? []) as CBTExam[];
  const attempts = (att?.items ?? []) as { exam_id: string; status: string; score: number | null; max_score: number | null }[];

  if (isLoading) return <Skeleton />;
  if (!exams.length) return <Empty title={KIND_COPY[kind].empty} sub={KIND_COPY[kind].sub} />;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {exams.map((e) => (
        <ExamCard key={e.id} exam={e} attempts={attempts.filter((a) => a.exam_id === e.id)} />
      ))}
    </div>
  );
}

function ExamCard({ exam, attempts }: { exam: CBTExam; attempts: { status: string; score: number | null; max_score: number | null }[] }) {
  const router = useRouter();
  const now = new Date();
  const start = exam.start_time ? new Date(exam.start_time) : null;
  const end = exam.end_time ? new Date(exam.end_time) : null;
  const upcoming = !!start && now < start;
  const closed = exam.status === "closed" || (!!end && now > end) || exam.status === "draft";
  const done = attempts.filter((a) => a.status === "submitted" || a.status === "graded");
  const inProgress = attempts.some((a) => a.status === "in_progress");
  const used = exam.max_attempts > 0 && done.length >= exam.max_attempts;
  const held = exam.hold_results && !exam.results_published_at;
  const last = done[0];
  const pct = last && last.max_score ? Math.round(((last.score ?? 0) / last.max_score) * 100) : null;

  let action: React.ReactNode;
  if (inProgress) action = <Cta onClick={() => router.push(`/dashboard/my-exams/${exam.id}/take`)} tone="green">Resume →</Cta>;
  else if (used) action = <p className="text-xs text-center text-slate-400">Completed</p>;
  else if (upcoming) action = <p className="text-xs text-center text-blue-600">Opens {formatDate(exam.start_time || "")}</p>;
  else if (closed) action = <p className="text-xs text-center text-slate-400">Closed</p>;
  else action = <Cta onClick={() => router.push(`/dashboard/my-exams/${exam.id}/take`)}>{done.length ? "Take again →" : "Start →"}</Cta>;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-lg bg-sky-50 border border-sky-100 flex items-center justify-center shrink-0">
          <MonitorCheck size={18} className="text-sky-600" />
        </div>
        {done.length > 0 && <span className="text-xs font-semibold text-emerald-600 flex items-center gap-1"><CheckCircle2 size={13} /> Done</span>}
      </div>
      <h3 className="text-sm font-bold text-slate-900 mb-1 line-clamp-2">{exam.title}</h3>
      {exam.description && <p className="text-xs text-slate-500 mb-3 line-clamp-2">{exam.description}</p>}
      <div className="space-y-1.5 mb-3 text-xs text-slate-500">
        <div className="flex items-center gap-1.5"><Clock size={12} />{exam.duration_minutes} min{start ? ` · ${formatDate(exam.start_time || "")}` : ""}</div>
        {exam.pass_percentage ? <div className="flex items-center gap-1.5"><Award size={12} /> Pass: {exam.pass_percentage}%</div> : null}
        {last && (held
          ? <div className="text-amber-600">Result pending release</div>
          : pct !== null && <div className="font-semibold text-slate-700">Your score: {pct}%</div>)}
      </div>
      <div className="mt-auto pt-3 border-t border-slate-100">{action}</div>
    </div>
  );
}

function Cta({ children, onClick, tone }: { children: React.ReactNode; onClick: () => void; tone?: "green" }) {
  return (
    <button onClick={onClick}
      className={cn("w-full text-sm font-semibold transition", tone === "green" ? "text-emerald-600 hover:text-emerald-700" : "text-brand-600 hover:text-brand-700")}>
      {children}
    </button>
  );
}

// ── Practice ──────────────────────────────────────────────────────────────────

function PracticeTab() {
  const router = useRouter();
  const { data, isLoading } = useQuery({ queryKey: ["practice-subjects"], queryFn: cbtApi.practice.subjects });
  const { data: prog } = useQuery({ queryKey: ["my-progress"], queryFn: cbtApi.myProgress });
  const [subjectId, setSubjectId] = useState("");
  const [count, setCount] = useState(10);
  const [difficulty, setDifficulty] = useState("any");
  const subjects = data?.items ?? [];
  const chosen = subjects.find((s) => s.id === subjectId);

  const start = useMutation({
    mutationFn: () => cbtApi.practice.start({ subject_id: subjectId, count, difficulty }),
    onSuccess: (r) => router.push(`/dashboard/my-exams/${r.exam_id}/take`),
    onError: (e: any) => toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Couldn't start practice."),
  });

  const past = ((prog?.recent ?? []) as any[]).filter((r) => r.exam_type === "practice").slice(0, 8);

  if (isLoading) return <Skeleton />;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 bg-white rounded-2xl border border-slate-200 p-6">
        <h2 className="text-lg font-black text-slate-900 flex items-center gap-2"><Dumbbell size={18} className="text-brand-600" /> Practise on your own</h2>
        <p className="text-sm text-slate-500 mt-1 mb-5">Pick a subject and we'll make a fresh paper from the school's question bank. Your score is saved to your progress.</p>
        {subjects.length === 0 ? (
          <p className="text-sm text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-4">No practice questions are available yet. Ask your teacher to add questions to the question bank.</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="label">Subject</label>
              <select className="input" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
                <option value="">Choose a subject…</option>
                {subjects.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.question_count} questions)</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Questions</label>
                <select className="input" value={count} onChange={(e) => setCount(Number(e.target.value))}>
                  {[5, 10, 20, 30, 40].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Difficulty</label>
                <select className="input" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                  <option value="any">Mixed</option><option value="easy">Easy</option>
                  <option value="medium">Medium</option><option value="hard">Hard</option>
                </select>
              </div>
            </div>
            {chosen && count > chosen.question_count && (
              <p className="text-xs text-amber-600">Only {chosen.question_count} questions are available for this subject, so the paper will be shorter.</p>
            )}
            <button disabled={!subjectId || start.isPending} onClick={() => start.mutate()}
              className="w-full bg-brand-600 hover:bg-brand-700 disabled:bg-slate-300 text-white font-semibold py-3 rounded-xl transition flex items-center justify-center gap-2">
              {start.isPending ? <Loader2 size={16} className="animate-spin" /> : null} Start practice
            </button>
          </div>
        )}
      </div>

      <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6">
        <h3 className="text-sm font-bold text-slate-800 mb-3">Recent practice</h3>
        {past.length === 0 ? <p className="text-sm text-slate-400">Nothing yet. Your practice scores will show here.</p> : (
          <ul className="divide-y divide-slate-100">
            {past.map((r) => (
              <li key={r.attempt_id} className="py-2.5 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{r.subject_name || r.title}</p>
                  <p className="text-[11px] text-slate-400">{r.submitted_at ? formatDate(r.submitted_at) : ""}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={cn("text-sm font-bold", (r.percentage ?? 0) >= 50 ? "text-emerald-600" : "text-red-600")}>{r.percentage ?? "—"}%</span>
                  <button onClick={() => router.push(`/dashboard/my-exams/review/${r.attempt_id}`)} aria-label="Review answers" className="text-slate-400 hover:text-brand-600"><BookOpenCheck size={16} /></button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Progress ──────────────────────────────────────────────────────────────────

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) return <span className="text-[11px] text-slate-300">not enough data</span>;
  const w = 96, h = 28;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - (Math.min(100, Math.max(0, v)) / 100) * h}`).join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible" aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" className="text-brand-600" />
    </svg>
  );
}

const TYPE_NAME: Record<string, string> = { exam: "Exams", test: "Tests", mock: "Mock", practice: "Practice" };

function ProgressTab() {
  const { data, isLoading } = useQuery({ queryKey: ["my-progress"], queryFn: cbtApi.myProgress });
  if (isLoading) return <Skeleton />;
  const o = data?.overall;
  if (!o || o.taken === 0) return <Empty title="No results yet" sub="Take an exam, a test or a practice paper and your scores will build up here." />;
  const subjects = (data.subjects ?? []) as any[];
  const byType = data.by_type ?? {};
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Tile label="Papers taken" value={String(o.taken)} />
        <Tile label="Average" value={o.average != null ? `${o.average}%` : "—"} />
        <Tile label="Best score" value={o.best != null ? `${o.best}%` : "—"} />
        <Tile label="Awaiting release" value={String(o.pending_results)} />
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-bold text-slate-800">Overall trend</h3>
          <span className="text-[11px] text-slate-400">last {o.trend.length} results</span>
        </div>
        <Bars values={o.trend} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Object.keys(TYPE_NAME).map((t) => (
          <div key={t} className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">{TYPE_NAME[t]}</p>
            <p className="text-xl font-black text-slate-900">{byType[t]?.average != null ? `${byType[t].average}%` : "—"}</p>
            <p className="text-[11px] text-slate-400">{byType[t]?.taken ?? 0} taken</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">By subject</h3></div>
        <ul className="divide-y divide-slate-100">
          {subjects.map((s) => (
            <li key={s.subject_id ?? "general"} className="px-5 py-3 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-slate-800 truncate">{s.name}</p>
                <p className="text-[11px] text-slate-400">{s.taken} taken · best {s.best}%</p>
              </div>
              <Spark values={s.trend} />
              <div className="w-24">
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden"><div className={cn("h-full", s.average >= 50 ? "bg-emerald-500" : "bg-amber-500")} style={{ width: `${s.average}%` }} /></div>
                <p className="text-[11px] text-slate-500 mt-1 text-right font-semibold">{s.average}% avg</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-100"><h3 className="text-sm font-bold text-slate-800">History</h3></div>
        <ul className="divide-y divide-slate-100">
          {(data.recent as any[]).map((r) => (
            <li key={r.attempt_id} className="px-5 py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm text-slate-800 truncate"><span className="badge bg-slate-50 text-slate-600 border-slate-200 mr-2 uppercase text-[9px]">{r.exam_type}</span>{r.title}</p>
                <p className="text-[11px] text-slate-400">{r.submitted_at ? formatDate(r.submitted_at) : ""}</p>
              </div>
              <span className={cn("text-sm font-bold shrink-0", r.pending ? "text-amber-600" : (r.percentage ?? 0) >= 50 ? "text-emerald-600" : "text-red-600")}>
                {r.pending ? "Pending" : `${r.percentage ?? "—"}%`}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Bars({ values }: { values: number[] }) {
  return (
    <div className="flex items-end gap-1.5 h-32" role="img" aria-label="Recent scores">
      {values.map((v, i) => (
        <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
          <span className="text-[10px] text-slate-400 mb-1">{Math.round(v)}</span>
          <div className={cn("w-full rounded-t", v >= 50 ? "bg-emerald-500" : "bg-amber-500")} style={{ height: `${Math.max(4, v)}%` }} />
        </div>
      ))}
    </div>
  );
}

// ── bits ──────────────────────────────────────────────────────────────────────

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">{label}</p>
      <p className="text-2xl font-black text-slate-900">{value}</p>
    </div>
  );
}

function Skeleton() {
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-40 bg-slate-100 rounded-xl animate-pulse" />)}</div>;
}

function Empty({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-16 text-slate-400 text-center px-4">
      <MonitorCheck size={40} className="mb-3 opacity-40" />
      <p className="font-semibold">{title}</p>
      <p className="text-sm mt-1">{sub}</p>
    </div>
  );
}
