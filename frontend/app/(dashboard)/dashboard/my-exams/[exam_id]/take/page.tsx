"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Loader2, ChevronLeft, ChevronRight, Clock, CheckCircle, AlertCircle, ShieldCheck,
  Timer, Maximize2, BookOpenCheck, RotateCcw,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { cbtApi, uploadApi } from "@/lib/api";
import { isIdle, makeDebounce } from "@/lib/examRoom";
import { renderQuestionHtml } from "@/components/inputs/MathTools";
import type { CBTExam } from "@/types";


interface Question {
  id: string;
  question_text: string;
  question_type: string;
  options?: ({ key: string; text: string } | string)[];
  answer_type?: string;
  points?: number;
}

interface Attempt {
  id: string;
  exam_id: string;
  status: string;
  started_at: string;
  deadline?: string | null;
}

interface Outcome { score: number | null; max_score: number | null }

const TYPE_LABEL: Record<string, string> = { exam: "Exam", test: "Test", mock: "Mock exam", practice: "Practice" };

const apiMessage = (err: any, fallback: string) => {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object" && d.message) return String(d.message);
  return fallback;
};

export default function TakeExamPage() {
  const params = useParams();
  const examId = params.exam_id as string;

  const [stage, setStage] = useState<"loading" | "intro" | "sitting" | "done" | "error">("loading");
  const [exam, setExam] = useState<CBTExam | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [uploadingFor, setUploadingFor] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);

  // Exam-room state
  const [idleWarn, setIdleWarn] = useState(false);
  const [leftTab, setLeftTab] = useState(false);
  const [notFullscreen, setNotFullscreen] = useState(false);

  const kind = exam?.exam_type || "exam";
  const secure = kind !== "practice";
  const submittedRef = useRef(false);
  const lastActive = useRef(Date.now());
  const idleWarnRef = useRef(false);
  const deadlineMs = useRef<number | null>(null);
  const answersRef = useRef(answers);
  answersRef.current = answers;

  // ── load ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const e = await cbtApi.exams.get(examId);
        const q = await cbtApi.questions.list(examId, false);
        setExam(e);
        setQuestions(q.items || q || []);
        setStage("intro");
      } catch (err: any) {
        setError(apiMessage(err, "Failed to load exam."));
        setStage("error");
      }
    })();
  }, [examId]);

  const storeKey = attempt ? `cbt-answers-${attempt.id}` : null;
  useEffect(() => {
    if (!storeKey) return;
    try { sessionStorage.setItem(storeKey, JSON.stringify(answers)); } catch { /* storage unavailable */ }
  }, [answers, storeKey]);

  const send = useCallback((type: "idle" | "blur" | "paste") => {
    if (attempt) cbtApi.attempts.event(attempt.id, type);
  }, [attempt]);

  // ── start ───────────────────────────────────────────────────────────────────
  const begin = async () => {
    setStarting(true);
    try {
      const a: Attempt = await cbtApi.attempts.start(examId, "");
      setAttempt(a);
      deadlineMs.current = a.deadline
        ? new Date(a.deadline).getTime()
        : exam?.duration_minutes && a.started_at
          ? new Date(a.started_at).getTime() + exam.duration_minutes * 60_000
          : null;
      try {
        const saved = sessionStorage.getItem(`cbt-answers-${a.id}`);
        if (saved) setAnswers(JSON.parse(saved));
      } catch { /* ignore */ }
      lastActive.current = Date.now();
      setStage("sitting");
      if (secure) {
        try { await document.documentElement.requestFullscreen?.(); } catch { /* not allowed on this device */ }
      }
    } catch (err: any) {
      const m = apiMessage(err, "Failed to start.");
      setError(m);
      toast.error(m);
    } finally {
      setStarting(false);
    }
  };

  // ── submit ──────────────────────────────────────────────────────────────────
  const submit = useCallback(async (auto = false) => {
    if (!attempt || submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    setConfirmOpen(false);
    try {
      const body = questions.map((q) => ({ question_id: q.id, answer_text: answersRef.current[q.id] || "" }));
      const res = await cbtApi.attempts.submit(attempt.id, body);
      setOutcome({ score: res.score ?? null, max_score: res.max_score ?? null });
      try { sessionStorage.removeItem(`cbt-answers-${attempt.id}`); } catch { /* ignore */ }
      try { if (document.fullscreenElement) await document.exitFullscreen(); } catch { /* ignore */ }
      setStage("done");
      toast.success(auto ? "Time's up. Your answers were submitted." : "Submitted.");
    } catch (err: any) {
      submittedRef.current = false;
      const m = apiMessage(err, "Failed to submit.");
      setError(m);
      toast.error(m);
    } finally {
      setSubmitting(false);
    }
  }, [attempt, questions]);

  // ── timer (against the server deadline, so reloads and sleeping devices stay honest) ──
  useEffect(() => {
    if (stage !== "sitting" || deadlineMs.current === null) return;
    const tick = () => {
      const left = Math.max(0, Math.round((deadlineMs.current! - Date.now()) / 1000));
      setRemaining(left);
      if (left <= 0) submit(true);
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [stage, submit]);

  // ── inactivity: warn after 3 minutes of no activity ─────────────────────────
  useEffect(() => {
    if (stage !== "sitting") return;
    const bump = () => {
      lastActive.current = Date.now();
      if (idleWarnRef.current) return; // the warning must be dismissed explicitly
    };
    const events = ["mousemove", "mousedown", "keydown", "touchstart", "scroll", "click", "input"];
    events.forEach((ev) => window.addEventListener(ev, bump, { passive: true }));
    const baseTitle = document.title;
    const check = setInterval(() => {
      if (!idleWarnRef.current && isIdle(Date.now(), lastActive.current)) {
        idleWarnRef.current = true;
        setIdleWarn(true);
        document.title = "⚠ Are you still there? — Exam";
        send("idle");
      }
    }, 5000);
    return () => {
      events.forEach((ev) => window.removeEventListener(ev, bump));
      clearInterval(check);
      document.title = baseTitle;
    };
  }, [stage, send]);

  const dismissIdle = () => {
    idleWarnRef.current = false;
    lastActive.current = Date.now();
    setIdleWarn(false);
    document.title = "Exam";
  };

  // ── exam-room security (exams, tests and mocks; practice stays relaxed) ─────
  useEffect(() => {
    if (stage !== "sitting" || !secure) return;
    const once = makeDebounce();
    const left = () => { setLeftTab(true); if (once()) send("blur"); };
    const onHide = () => { if (document.hidden) left(); };
    const onBlur = () => left();
    const onFs = () => { if (!document.fullscreenElement) setNotFullscreen(true); else setNotFullscreen(false); };
    const block = (e: Event) => {
      e.preventDefault();
      if (e.type === "paste" || e.type === "copy" || e.type === "cut") send("paste");
    };
    const beforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("blur", onBlur);
    document.addEventListener("fullscreenchange", onFs);
    ["copy", "cut", "paste", "contextmenu", "dragstart"].forEach((t) => document.addEventListener(t, block));
    window.addEventListener("beforeunload", beforeUnload);
    return () => {
      document.removeEventListener("visibilitychange", onHide);
      window.removeEventListener("blur", onBlur);
      document.removeEventListener("fullscreenchange", onFs);
      ["copy", "cut", "paste", "contextmenu", "dragstart"].forEach((t) => document.removeEventListener(t, block));
      window.removeEventListener("beforeunload", beforeUnload);
    };
  }, [stage, secure, send]);

  const uploadAnswerFile = async (qid: string, f?: File) => {
    if (!f) return;
    setUploadingFor(qid);
    try {
      const { url } = await uploadApi.examAnswer(f);
      setAnswers((p) => ({ ...p, [qid]: url }));
    } catch (e: any) {
      toast.error(apiMessage(e, "Upload failed."));
    } finally { setUploadingFor(null); }
  };

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  const answered = questions.filter((q) => (answers[q.id] || "").trim() !== "").length;
  const q = questions[idx];
  const qType = String(q?.question_type || "").toLowerCase();
  const isLast = idx === questions.length - 1;

  // ── screens ─────────────────────────────────────────────────────────────────
  if (stage === "loading") {
    return <div className="p-8 flex items-center justify-center min-h-[60vh]"><Loader2 className="w-8 h-8 animate-spin text-brand-600" /></div>;
  }

  if (stage === "error" || !exam || questions.length === 0) {
    return (
      <div className="p-4 sm:p-8 max-w-3xl mx-auto">
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <AlertCircle className="w-12 h-12 mx-auto mb-3 text-amber-600" />
          <h2 className="text-lg font-bold text-slate-900 mb-2">Could not load exam</h2>
          <p className="text-slate-500 text-sm mb-4">{error || "This exam has no questions yet."}</p>
          <Link href="/dashboard/my-exams" className="text-brand-600 hover:underline text-sm font-semibold">Back to Exam Portal</Link>
        </div>
      </div>
    );
  }

  if (stage === "intro") {
    return (
      <div className="p-4 sm:p-8 max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl border border-slate-200 p-6 sm:p-8">
          <span className="badge bg-indigo-50 text-indigo-700 border-indigo-200 uppercase text-[10px]">{TYPE_LABEL[kind] || "Exam"}</span>
          <h1 className="text-2xl font-black text-slate-900 mt-2 mb-1">{exam.title}</h1>
          {exam.description && <p className="text-slate-600 text-sm mb-4">{exam.description}</p>}
          <div className="grid grid-cols-3 gap-3 my-5">
            <Stat label="Questions" value={String(questions.length)} />
            <Stat label="Time" value={exam.duration_minutes ? `${exam.duration_minutes} min` : "None"} />
            <Stat label="Pass mark" value={exam.pass_percentage ? `${exam.pass_percentage}%` : "—"} />
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 text-sm text-slate-700 space-y-2 mb-6">
            <p className="font-semibold flex items-center gap-2"><ShieldCheck size={16} className="text-emerald-600" /> Before you start</p>
            <ul className="list-disc pl-5 space-y-1 text-[13px]">
              <li>The timer starts when you press Start and keeps running if you leave.</li>
              <li>If you do nothing for <b>3 minutes</b> you will get an inactivity warning.</li>
              {secure && <li>Stay on this page. Leaving the tab, copying or pasting is recorded and your teacher can see it.</li>}
              {secure && <li>The exam opens in full screen where your device allows it.</li>}
              {!secure && <li>This is practice. Your score is saved to your progress and you can review the answers afterwards.</li>}
            </ul>
          </div>
          {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
          <button onClick={begin} disabled={starting}
            className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white font-semibold py-3 rounded-xl transition">
            {starting ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : `Start ${TYPE_LABEL[kind]?.toLowerCase() || "exam"}`}
          </button>
          <Link href="/dashboard/my-exams" className="block text-center text-brand-600 hover:underline text-sm font-semibold mt-4">Back to Exam Portal</Link>
        </div>
      </div>
    );
  }

  if (stage === "done") {
    const held = exam.hold_results && !exam.results_published_at;
    const pct = outcome?.max_score ? Math.round(((outcome.score ?? 0) / outcome.max_score) * 1000) / 10 : null;
    const hasSubjective = questions.some((x) => ["short_answer", "long_answer"].includes(String(x.question_type).toLowerCase()));
    const passed = pct !== null && exam.pass_percentage ? pct >= exam.pass_percentage : null;
    return (
      <div className="p-4 sm:p-8 max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center">
          <CheckCircle className="w-16 h-16 mx-auto mb-4 text-emerald-600" />
          <h2 className="text-2xl font-black text-slate-900 mb-1">{TYPE_LABEL[kind] || "Exam"} submitted</h2>
          {held ? (
            <p className="text-slate-500 text-sm mb-6">Your result will appear once your teacher releases it.</p>
          ) : (
            <>
              {pct !== null && (
                <div className="my-5">
                  <p className={cn("text-5xl font-black", passed === false ? "text-red-600" : "text-emerald-600")}>{pct}%</p>
                  <p className="text-slate-500 text-sm mt-1">{outcome?.score} out of {outcome?.max_score} marks{passed !== null && (passed ? " · Passed" : " · Below the pass mark")}</p>
                </div>
              )}
              {hasSubjective && <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-2 mb-4">Written answers are marked by your teacher, so this score may rise.</p>}
            </>
          )}
          <div className="flex flex-wrap gap-2 justify-center">
            {kind === "practice" && attempt && (
              <Link href={`/dashboard/my-exams/review/${attempt.id}`} className="inline-flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-semibold px-4 py-2 rounded-lg">
                <BookOpenCheck size={15} /> Review answers
              </Link>
            )}
            <Link href="/dashboard/my-exams?tab=progress" className="inline-flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-semibold px-4 py-2 rounded-lg">My progress</Link>
            <Link href={kind === "practice" ? "/dashboard/my-exams?tab=practice" : "/dashboard/my-exams"} className="inline-flex items-center gap-2 border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-semibold px-4 py-2 rounded-lg">
              {kind === "practice" ? <><RotateCcw size={15} /> Practise again</> : "Back to Exam Portal"}
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // sitting
  return (
    <div className={cn("p-4 sm:p-8 max-w-4xl mx-auto", secure && "select-none")}>
      <div className="flex items-center justify-between gap-3 mb-5 sticky top-0 z-10 bg-slate-50/95 backdrop-blur py-2">
        <div className="min-w-0">
          <span className="badge bg-indigo-50 text-indigo-700 border-indigo-200 uppercase text-[10px]">{TYPE_LABEL[kind]}</span>
          <h1 className="text-lg sm:text-2xl font-bold text-slate-900 truncate">{exam.title}</h1>
        </div>
        {remaining !== null && (
          <div className={cn("text-lg font-bold px-3 py-1.5 rounded-lg flex items-center gap-2 shrink-0",
            remaining <= 60 ? "bg-red-100 text-red-700 animate-pulse" : "bg-slate-100 text-slate-700")}>
            <Clock size={16} /> {fmt(remaining)}
          </div>
        )}
      </div>

      {secure && leftTab && (
        <div className="mb-4 rounded-lg bg-amber-50 border border-amber-300 p-3 text-sm text-amber-800 flex items-center justify-between gap-3">
          <span>You left the exam page. This has been recorded for your teacher. Please stay on this page.</span>
          <button onClick={() => setLeftTab(false)} className="text-xs font-semibold underline shrink-0">OK</button>
        </div>
      )}
      {secure && notFullscreen && (
        <div className="mb-4 rounded-lg bg-slate-100 border border-slate-300 p-3 text-sm text-slate-700 flex items-center justify-between gap-3">
          <span>The exam works best in full screen.</span>
          <button onClick={() => document.documentElement.requestFullscreen?.().catch(() => undefined)}
            className="inline-flex items-center gap-1 text-xs font-semibold underline shrink-0"><Maximize2 size={13} /> Full screen</button>
        </div>
      )}

      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-600">Question {idx + 1} of {questions.length}</span>
          <span className="text-xs text-slate-500">{answered} answered</span>
        </div>
        <div className="w-full bg-slate-200 rounded-full h-2">
          <div className="bg-brand-600 h-2 rounded-full transition-all" style={{ width: `${((idx + 1) / questions.length) * 100}%` }} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 sm:p-6 mb-5">
        <h2 className="text-lg font-bold text-slate-900 mb-4">
          <span dangerouslySetInnerHTML={{ __html: renderQuestionHtml(q.question_text) }} />
        </h2>

        {qType === "mcq" && q.options && (
          <div className="space-y-2">
            {q.options.map((raw, i) => {
              const key = typeof raw === "string" ? raw : raw.key;
              const text = typeof raw === "string" ? raw : raw.text;
              const on = answers[q.id] === key;
              return (
                <label key={i} className={cn("flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition",
                  on ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:bg-slate-50")}>
                  <input type="radio" name={`question-${q.id}`} value={key} checked={on}
                    onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))} className="w-4 h-4" />
                  <span className="text-sm text-slate-700"><span className="font-bold uppercase text-slate-400 mr-2">{key}</span>{text}</span>
                </label>
              );
            })}
          </div>
        )}

        {qType === "true_false" && (
          <div className="space-y-2">
            {["True", "False"].map((o) => {
              const on = answers[q.id] === o.toLowerCase();
              return (
                <label key={o} className={cn("flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition",
                  on ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:bg-slate-50")}>
                  <input type="radio" name={`question-${q.id}`} value={o.toLowerCase()} checked={on}
                    onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))} className="w-4 h-4" />
                  <span className="text-sm text-slate-700">{o}</span>
                </label>
              );
            })}
          </div>
        )}

        {(qType === "short_answer" || qType === "long_answer") && q.answer_type !== "file" && (
          <textarea aria-label="Your answer" value={answers[q.id] || ""}
            onChange={(e) => setAnswers((p) => ({ ...p, [q.id]: e.target.value }))}
            rows={qType === "long_answer" ? 10 : 3} className="input w-full select-text" placeholder="Type your answer here" />
        )}
        {(qType === "short_answer" || qType === "long_answer") && q.answer_type === "file" && (
          <div>
            <label className="flex items-center gap-2 px-4 py-3 rounded-lg border border-dashed border-slate-300 hover:bg-slate-50 cursor-pointer text-sm text-slate-600 w-fit">
              {uploadingFor === q.id ? "Uploading…" : answers[q.id] ? "Replace file" : "Choose file to upload"}
              <input type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,image/png,image/jpeg,image/webp,image/gif"
                onChange={(e) => uploadAnswerFile(q.id, e.target.files?.[0])} />
            </label>
            {answers[q.id] && <p className="text-xs text-emerald-700 mt-2">File attached ✓</p>}
            <p className="text-[11px] text-slate-400 mt-1">PDF, Word, text or photo, up to 15 MB.</p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-3">
        <button onClick={() => setIdx((i) => Math.max(0, i - 1))} disabled={idx === 0}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 text-sm font-semibold text-slate-700">
          <ChevronLeft size={16} /> Previous
        </button>
        {isLast ? (
          <button onClick={() => setConfirmOpen(true)} disabled={submitting}
            className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-sm font-semibold">
            {submitting ? <Loader2 size={16} className="animate-spin" /> : <CheckCircle size={16} />} Submit
          </button>
        ) : (
          <button onClick={() => setIdx((i) => Math.min(questions.length - 1, i + 1))}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 text-sm font-semibold text-slate-700">
            Next <ChevronRight size={16} />
          </button>
        )}
      </div>

      <div className="mt-6 flex flex-wrap gap-1.5" aria-label="Question navigator">
        {questions.map((qq, i) => (
          <button key={qq.id} onClick={() => setIdx(i)} aria-label={`Go to question ${i + 1}`}
            className={cn("w-8 h-8 rounded-md text-xs font-bold border transition",
              i === idx ? "bg-brand-600 text-white border-brand-600"
                : (answers[qq.id] || "").trim() ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                  : "bg-white text-slate-500 border-slate-200 hover:bg-slate-50")}>
            {i + 1}
          </button>
        ))}
      </div>
      {!isLast && (
        <div className="mt-4 text-center">
          <button onClick={() => setConfirmOpen(true)} className="text-xs font-semibold text-slate-500 hover:text-slate-800 underline">Finish and submit now</button>
        </div>
      )}

      {error && <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200"><p className="text-sm text-red-700">{error}</p></div>}

      {confirmOpen && (
        <Overlay>
          <h3 className="text-lg font-bold text-slate-900 mb-2">Submit your {TYPE_LABEL[kind]?.toLowerCase()}?</h3>
          <p className="text-sm text-slate-600 mb-5">
            {answered < questions.length
              ? <>You have answered <b>{answered}</b> of <b>{questions.length}</b> questions. <b>{questions.length - answered}</b> unanswered will score zero.</>
              : <>You have answered all {questions.length} questions.</>}
            {" "}You can't change your answers after submitting.
          </p>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setConfirmOpen(false)} className="px-4 py-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50">Keep working</button>
            <button onClick={() => submit(false)} className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold">Submit now</button>
          </div>
        </Overlay>
      )}

      {idleWarn && (
        <Overlay tone="warn">
          <div className="flex items-start gap-3">
            <Timer className="text-amber-600 shrink-0 mt-0.5" size={22} />
            <div>
              <h3 className="text-lg font-bold text-slate-900 mb-1">Are you still there?</h3>
              <p className="text-sm text-slate-600">
                You haven't done anything for 3 minutes. Your timer is still running{remaining !== null ? ` (${fmt(remaining)} left)` : ""}.
                {secure ? " This has been recorded for your teacher." : ""}
              </p>
            </div>
          </div>
          <button onClick={dismissIdle} className="mt-5 w-full bg-brand-600 hover:bg-brand-700 text-white font-semibold py-2.5 rounded-lg">I'm still here</button>
        </Overlay>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
      <p className="text-lg font-black text-slate-900">{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">{label}</p>
    </div>
  );
}

function Overlay({ children, tone }: { children: React.ReactNode; tone?: "warn" }) {
  return (
    <div role="alertdialog" aria-modal="true" className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={cn("bg-white rounded-2xl shadow-2xl w-full max-w-md p-6 border-t-4", tone === "warn" ? "border-amber-500" : "border-brand-500")}>
        {children}
      </div>
    </div>
  );
}
