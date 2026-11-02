"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  FileText, ClipboardList, FlaskConical, Dumbbell, TrendingUp, Trophy, Flame, Target,
  Clock, Play, Sparkles, ChevronRight, Star,
} from "lucide-react";
import { cbtApi } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";
import { useAuthStore } from "@/lib/store";
import type { CBTExam } from "@/types";

type Tab = "home" | "exam" | "test" | "mock" | "practice" | "progress";

const BLOCKS: { key: Exclude<Tab, "home">; label: string; sub: string; icon: typeof FileText; grad: string }[] = [
  { key: "exam", label: "Exams", sub: "School exams", icon: FileText, grad: "from-sky-500 to-blue-600" },
  { key: "test", label: "Tests", sub: "Class tests", icon: ClipboardList, grad: "from-emerald-500 to-green-600" },
  { key: "mock", label: "Mock", sub: "Rehearse the real thing", icon: FlaskConical, grad: "from-amber-500 to-orange-600" },
  { key: "practice", label: "Practice", sub: "JAMB · WAEC · NECO", icon: Dumbbell, grad: "from-rose-500 to-pink-600" },
  { key: "progress", label: "My Progress", sub: "Scores & trends", icon: TrendingUp, grad: "from-violet-500 to-purple-600" },
];

function useKind(kind: "exam" | "test" | "mock") {
  return useQuery({
    queryKey: ["my-exams", kind],
    queryFn: () => cbtApi.exams.list({ for_me: true, exam_type: kind, page: 1, page_size: 100 }),
  });
}

function streakDays(dates: string[]): number {
  const days = new Set(dates.map((d) => new Date(d).toDateString()));
  let n = 0;
  const d = new Date();
  if (!days.has(d.toDateString())) d.setDate(d.getDate() - 1);
  while (days.has(d.toDateString())) { n++; d.setDate(d.getDate() - 1); }
  return n;
}

function Ring({ pct, size = 64, color = "#fff", track = "rgba(255,255,255,.25)" }: { pct: number; size?: number; color?: string; track?: string }) {
  const r = (size - 8) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, pct));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90 shrink-0" aria-hidden>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth="7" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c - (v / 100) * c} />
    </svg>
  );
}

export function ExamHome({ go }: { go: (t: Tab) => void }) {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const exam = useKind("exam"), test = useKind("test"), mock = useKind("mock");
  const { data: att } = useQuery({ queryKey: ["my-attempts"], queryFn: () => cbtApi.attempts.list() });
  const { data: prog } = useQuery({ queryKey: ["my-progress"], queryFn: cbtApi.myProgress });

  const attempts = (att?.items ?? []) as { exam_id: string; status: string }[];
  const lists = { exam: (exam.data?.items ?? []) as CBTExam[], test: (test.data?.items ?? []) as CBTExam[], mock: (mock.data?.items ?? []) as CBTExam[] };
  const now = new Date();

  const isOpen = (e: CBTExam) => {
    const s = e.start_time ? new Date(e.start_time) : null, en = e.end_time ? new Date(e.end_time) : null;
    if (e.status === "closed" || e.status === "draft") return false;
    if (s && now < s) return false;
    if (en && now > en) return false;
    if ((e as any).is_live === false) return false;
    const done = attempts.filter((a) => a.exam_id === e.id && (a.status === "submitted" || a.status === "graded")).length;
    return !(e.max_attempts > 0 && done >= e.max_attempts);
  };
  const isUpcoming = (e: CBTExam) => !!e.start_time && now < new Date(e.start_time) && e.status !== "closed" && e.status !== "draft";

  const all = [...lists.exam, ...lists.test, ...lists.mock];
  const open = all.filter(isOpen);
  const upcoming = all.filter(isUpcoming).sort((a, b) => +new Date(a.start_time!) - +new Date(b.start_time!));
  const countOpen = (k: "exam" | "test" | "mock") => lists[k].filter(isOpen).length;

  const o = prog?.overall;
  const recent = ((prog?.recent ?? []) as any[]).filter((r) => !r.pending).slice(0, 4);
  const streak = streakDays(((prog?.recent ?? []) as any[]).map((r) => r.submitted_at).filter(Boolean));
  const subjects = ((prog?.subjects ?? []) as any[]).filter((s) => s.taken > 0);
  const best = [...subjects].sort((a, b) => b.average - a.average)[0];
  const weak = [...subjects].sort((a, b) => a.average - b.average)[0];
  const first = user?.full_name?.split(" ")[0] ?? "there";
  const avg = o?.average ?? 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-6 sm:p-8 text-white shadow-lg">
        <div className="absolute -right-10 -top-10 w-56 h-56 rounded-full bg-white/10" />
        <div className="absolute right-24 -bottom-16 w-48 h-48 rounded-full bg-white/10" />
        <div className="relative flex flex-wrap items-center gap-6">
          <div className="flex-1 min-w-[14rem]">
            <p className="text-sm font-semibold text-white/80 flex items-center gap-1.5"><Sparkles size={16} /> Exam Portal</p>
            <h2 className="text-2xl sm:text-3xl font-black mt-1">Ready when you are, {first}!</h2>
            <p className="text-white/85 mt-1">
              {open.length > 0
                ? `You have ${open.length} paper${open.length === 1 ? "" : "s"} open right now.`
                : upcoming.length > 0 ? `Next up: ${upcoming[0].title}.` : "Nothing scheduled. Why not sharpen up with some practice?"}
            </p>
            <button onClick={() => go(open.length ? "exam" : "practice")}
              className="mt-4 inline-flex items-center gap-2 bg-white text-violet-700 font-bold px-5 py-2.5 rounded-xl hover:scale-105 transition-transform">
              <Play size={16} className="fill-current" /> {open.length ? "Go to my papers" : "Start practising"}
            </button>
          </div>
          <div className="flex items-center gap-4">
            <div className="relative">
              <Ring pct={avg} size={92} />
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-xl font-black leading-none">{o?.average != null ? `${o.average}%` : "—"}</span>
                <span className="text-[11px] font-semibold text-white/80">average</span>
              </div>
            </div>
          </div>
        </div>
        <div className="relative grid grid-cols-3 gap-3 mt-6">
          {[
            { icon: Target, label: "Papers taken", value: o?.taken ?? 0 },
            { icon: Trophy, label: "Best score", value: o?.best != null ? `${o.best}%` : "—" },
            { icon: Flame, label: "Day streak", value: streak },
          ].map(({ icon: I, label, value }) => (
            <div key={label} className="rounded-2xl bg-white/15 backdrop-blur px-3 py-3 text-center">
              <I size={20} className="mx-auto mb-1" />
              <div className="text-xl font-black leading-none">{value}</div>
              <div className="text-xs font-semibold text-white/80 mt-1">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Colour blocks */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        {BLOCKS.map(({ key, label, sub, icon: Icon, grad }) => {
          const n = key === "exam" || key === "test" || key === "mock" ? countOpen(key) : null;
          return (
            <button key={key} onClick={() => go(key)}
              className={cn("group relative overflow-hidden rounded-2xl bg-gradient-to-br p-4 sm:p-5 text-left text-white shadow-md hover:shadow-xl hover:-translate-y-1 transition-all", grad)}>
              <Icon size={64} strokeWidth={1.5} className="absolute -right-3 -bottom-3 opacity-20 group-hover:scale-110 transition-transform" />
              <Icon size={28} strokeWidth={2.4} className="mb-3 relative" />
              <p className="text-lg font-black relative">{label}</p>
              <p className="text-xs text-white/85 font-medium relative">{sub}</p>
              {n !== null && (
                <span className={cn("absolute top-3 right-3 text-xs font-black px-2 py-0.5 rounded-full",
                  n > 0 ? "bg-white text-slate-800 animate-pulse" : "bg-white/25")}>
                  {n > 0 ? `${n} open` : "none"}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Up next */}
        <div className="rounded-2xl bg-white border border-slate-200 p-5">
          <h3 className="text-base font-black text-slate-900 flex items-center gap-2 mb-3"><Clock size={18} className="text-sky-600" /> Up next</h3>
          {open.length === 0 && upcoming.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">Nothing scheduled right now. Check back soon.</p>
          ) : (
            <ul className="space-y-2">
              {open.slice(0, 3).map((e) => (
                <li key={e.id} className="flex items-center gap-3 rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3">
                  <span className="relative flex h-3 w-3 shrink-0"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" /><span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" /></span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{e.title}</p>
                    <p className="text-xs text-emerald-700 font-semibold">Open now · {e.duration_minutes} min</p>
                  </div>
                  <button onClick={() => router.push(`/dashboard/my-exams/${e.id}/take`)}
                    className="shrink-0 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold px-4 py-2 rounded-lg">Start</button>
                </li>
              ))}
              {upcoming.slice(0, 3).map((e) => (
                <li key={e.id} className="flex items-center gap-3 rounded-xl bg-sky-50 border border-sky-200 px-4 py-3">
                  <Clock size={16} className="text-sky-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{e.title}</p>
                    <p className="text-xs text-sky-700 font-semibold">Opens {formatDate(e.start_time || "")}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Latest results */}
        <div className="rounded-2xl bg-white border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-black text-slate-900 flex items-center gap-2"><Star size={18} className="text-amber-500" /> Latest results</h3>
            <button onClick={() => go("progress")} className="text-xs font-bold text-violet-600 flex items-center">All <ChevronRight size={14} /></button>
          </div>
          {recent.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">Take a paper and your score will light up here.</p>
          ) : (
            <ul className="grid grid-cols-2 gap-3">
              {recent.map((r) => {
                const p = r.percentage ?? 0, good = p >= 50;
                return (
                  <li key={r.attempt_id}>
                    <button onClick={() => router.push(`/dashboard/my-exams/review/${r.attempt_id}`)}
                      className={cn("w-full rounded-xl p-3 flex items-center gap-3 text-left border hover:shadow-md transition",
                        good ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200")}>
                      <div className="relative">
                        <Ring pct={p} size={52} color={good ? "#059669" : "#d97706"} track="rgba(0,0,0,.08)" />
                        <span className="absolute inset-0 flex items-center justify-center text-xs font-black text-slate-800">{p}%</span>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-900 truncate">{r.title}</p>
                        <p className="text-[11px] text-slate-500 uppercase font-semibold">{r.exam_type}</p>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* Strength / focus + practice */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-200 p-5">
          <p className="text-xs font-black uppercase tracking-wider text-emerald-700 flex items-center gap-1.5"><Trophy size={14} /> Your strongest</p>
          <p className="text-lg font-black text-slate-900 mt-1 truncate">{best?.name ?? "Take a paper to find out"}</p>
          {best && <p className="text-sm font-bold text-emerald-700">{best.average}% average</p>}
        </div>
        <div className="rounded-2xl bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 p-5">
          <p className="text-xs font-black uppercase tracking-wider text-amber-700 flex items-center gap-1.5"><Target size={14} /> Focus on</p>
          <p className="text-lg font-black text-slate-900 mt-1 truncate">{weak && weak !== best ? weak.name : "You're doing great"}</p>
          {weak && weak !== best && <p className="text-sm font-bold text-amber-700">{weak.average}% average · practise this</p>}
        </div>
        <button onClick={() => go("practice")}
          className="rounded-2xl bg-gradient-to-br from-rose-500 to-pink-600 text-white p-5 text-left hover:-translate-y-1 hover:shadow-xl transition-all">
          <p className="text-xs font-black uppercase tracking-wider text-white/85 flex items-center gap-1.5"><Dumbbell size={14} /> Quick practice</p>
          <p className="text-lg font-black mt-1">Beat your best score</p>
          <p className="text-sm text-white/85">Pick a subject and go →</p>
        </button>
      </div>
    </div>
  );
}
