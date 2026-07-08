"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Radio, Loader2, Plus, Video, Users, Lock, PlayCircle, X, Calendar, Play,
  GraduationCap, ListChecks, Sparkles, ArrowRight,
} from "lucide-react";
import { toast } from "sonner";
import {
  useLiveSessions,
  useStartLive,
  useLiveRecordings,
  useLiveTimetableToday,
  useStartLiveFromTimetable,
} from "@/hooks/useLive";
import { useAuthStore } from "@/lib/store";
import { timeAgo, resolveMediaUrl } from "@/lib/utils";
import { schoolApi } from "@/lib/api";
import { LiveUsageCard } from "@/components/live/LiveUsageCard";
import type { LiveSession, TimetableSlot } from "@/types";

type ClassOption = { id: string; name: string };

export default function CbtLivePage() {
  const { data: sessions = [], isLoading } = useLiveSessions(true);
  // Past sessions with recordings — replay archive for catch-up students.
  const { data: allSessions = [] } = useLiveSessions(false);
  const { data: slots = [] } = useLiveTimetableToday();
  const [showNew, setShowNew] = useState(false);
  const [playbackSession, setPlaybackSession] = useState<LiveSession | null>(null);

  const pastWithRecording = allSessions.filter((s) => !s.is_active && s.has_recording);
  // "Brand-new school" heuristic — show the guided getting-started panel
  // only when the org has literally nothing set up yet. As soon as there's
  // any timetable slot or any past session we switch to the normal
  // dashboard so we don't hide analytics behind an onboarding card.
  const isFirstTime = !isLoading && allSessions.length === 0 && slots.length === 0;

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
            <Link href="/dashboard/modules/school/cbt" className="hover:underline">CBT</Link>
            <span>/</span>
            <span className="text-brand-600 font-semibold">Livestream</span>
          </nav>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Radio className="w-6 h-6 text-rose-500" />
            Live Classes
          </h1>
          <p className="text-slate-500 text-sm mt-1">
            Start a live session as the host, or join one in progress.
          </p>
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold px-4 py-2 rounded-lg"
        >
          <Plus className="w-4 h-4" />
          Go Live
        </button>
      </header>

      {isFirstTime ? (
        <GettingStarted onStart={() => setShowNew(true)} />
      ) : (
        <>
          <LiveUsageCard />
          {slots.length > 0 && <TimetableToday slots={slots} />}

          {isLoading ? (
            <div className="flex items-center justify-center py-10 text-slate-400">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
          ) : sessions.length === 0 ? (
            <EmptyState onStart={() => setShowNew(true)} />
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sessions.map((s) => (
                <SessionCard key={s.id} session={s} />
              ))}
            </div>
          )}
        </>
      )}

      {pastWithRecording.length > 0 && (
        <section className="pt-4">
          <h2 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
            <PlayCircle className="w-4 h-4 text-brand-500" />
            Recorded sessions
          </h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {pastWithRecording.map((s) => (
              <RecordingCard key={s.id} session={s} onPlay={() => setPlaybackSession(s)} />
            ))}
          </div>
        </section>
      )}

      {showNew && <StartModal onClose={() => setShowNew(false)} />}
      {playbackSession && (
        <PlaybackModal session={playbackSession} onClose={() => setPlaybackSession(null)} />
      )}
    </div>
  );
}

function TimetableToday({ slots }: { slots: TimetableSlot[] }) {
  // Current slot first, then anything upcoming, then everything else. Keeps
  // the button the teacher actually wants at the top without losing context.
  const sorted = [...slots].sort((a, b) => {
    if (a.is_current && !b.is_current) return -1;
    if (!a.is_current && b.is_current) return 1;
    return a.start_time.localeCompare(b.start_time);
  });
  return (
    <section className="bg-white border border-slate-200 rounded-2xl p-5">
      <h2 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
        <Calendar className="w-4 h-4 text-brand-500" />
        Today's timetable
      </h2>
      <ul className="divide-y divide-slate-100">
        {sorted.map((s) => (
          <TimetableRow key={s.timetable_id} slot={s} />
        ))}
      </ul>
    </section>
  );
}

function TimetableRow({ slot }: { slot: TimetableSlot }) {
  const router = useRouter();
  const startFromSlot = useStartLiveFromTimetable();

  const onJoin = () => {
    if (slot.live_session_id) {
      router.push(`/dashboard/modules/school/cbt/live/${slot.live_session_id}`);
    }
  };

  const onGoLive = async () => {
    const s = await startFromSlot.mutateAsync(slot.timetable_id);
    router.push(`/dashboard/modules/school/cbt/live/${s.id}`);
  };

  const label = [slot.class_name, slot.subject_name].filter(Boolean).join(" — ") || "Lesson";

  return (
    <li className="flex items-center justify-between py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-500 mb-1">
          <span>{slot.start_time} – {slot.end_time}</span>
          {slot.is_current && (
            <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded-full">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              Now
            </span>
          )}
        </div>
        <p className="text-sm font-semibold text-slate-800 truncate">{label}</p>
      </div>
      <div className="shrink-0 flex items-center gap-2">
        {slot.live_session_id ? (
          <button
            onClick={onJoin}
            className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg"
          >
            <Play className="w-3.5 h-3.5" />
            Join
          </button>
        ) : slot.can_host ? (
          <button
            onClick={onGoLive}
            disabled={startFromSlot.isPending}
            className="inline-flex items-center gap-1.5 bg-white border border-rose-500 text-rose-600 hover:bg-rose-50 disabled:opacity-50 text-xs font-semibold px-3 py-1.5 rounded-lg"
          >
            {startFromSlot.isPending ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Radio className="w-3.5 h-3.5" />
            )}
            Go Live
          </button>
        ) : (
          <span className="text-xs text-slate-400">Not live yet</span>
        )}
      </div>
    </li>
  );
}

function RecordingCard({ session, onPlay }: { session: LiveSession; onPlay: () => void }) {
  return (
    <button
      onClick={onPlay}
      className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md hover:border-brand-200 transition-all text-left"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
          <PlayCircle className="w-3 h-3" />
          Recording
        </span>
        {session.class_id && (
          <span className="text-[10px] font-bold uppercase tracking-wide bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full">
            Class-only
          </span>
        )}
      </div>
      <h3 className="text-sm font-bold text-slate-800 line-clamp-2">{session.title}</h3>
      <footer className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
        <span className="truncate">{session.host_name || "Unknown host"}</span>
        <span>{session.ended_at ? timeAgo(session.ended_at) : "—"}</span>
      </footer>
    </button>
  );
}

function PlaybackModal({ session, onClose }: { session: LiveSession; onClose: () => void }) {
  const { data: recordings = [], isLoading } = useLiveRecordings(session.id);
  const latest = recordings[0];
  const duration = latest?.duration_seconds;
  const durationLabel = duration
    ? `${Math.floor(duration / 60)}m ${duration % 60}s`
    : null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
        <header className="flex items-center justify-between p-4 border-b border-slate-200">
          <div className="min-w-0">
            <h2 className="text-sm font-bold text-slate-800 truncate">{session.title}</h2>
            <p className="text-xs text-slate-500 flex items-center gap-2">
              <span>{session.host_name}</span>
              {durationLabel && (
                <>
                  <span className="text-slate-300">·</span>
                  <span>{durationLabel}</span>
                </>
              )}
              {session.ended_at && (
                <>
                  <span className="text-slate-300">·</span>
                  <span>{timeAgo(session.ended_at)}</span>
                </>
              )}
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-100 text-slate-500">
            <X className="w-4 h-4" />
          </button>
        </header>
        <div className="p-4 bg-black flex items-center justify-center min-h-[240px]">
          {isLoading ? (
            <Loader2 className="w-6 h-6 animate-spin text-white/60" />
          ) : !latest ? (
            <div className="text-center">
              <p className="text-white/80 text-sm font-medium">No recording available yet.</p>
              <p className="text-white/50 text-xs mt-1">The teacher may still be uploading.</p>
            </div>
          ) : (
            <video
              src={resolveMediaUrl(latest.file_url)}
              controls
              autoPlay
              className="w-full max-h-[70vh]"
            />
          )}
        </div>
      </div>
    </div>
  );
}

function SessionCard({ session }: { session: LiveSession }) {
  const { user } = useAuthStore();
  const isHost = user?.id === session.host_user_id;

  return (
    <Link
      href={`/dashboard/modules/school/cbt/live/${session.id}`}
      className="bg-white border border-slate-200 rounded-xl p-5 hover:shadow-md hover:border-rose-200 transition-all block group"
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wide bg-rose-50 text-rose-600 px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-pulse" />
          Live
        </span>
        {isHost && (
          <span className="text-[10px] font-bold uppercase tracking-wide bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">
            Your session
          </span>
        )}
      </div>
      <h3 className="text-sm font-bold text-slate-800 group-hover:text-rose-600 line-clamp-2 flex items-center gap-1.5">
        {session.title}
        {session.class_id && (
          <span title="Class-only" className="text-slate-400">
            <Lock className="w-3 h-3" />
          </span>
        )}
      </h3>
      {session.description && (
        <p className="text-xs text-slate-500 mt-1 line-clamp-2">{session.description}</p>
      )}
      <footer className="flex items-center justify-between mt-4 pt-3 border-t border-slate-100 text-xs text-slate-500">
        <span className="truncate">{session.host_name || "Unknown host"}</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Users className="w-3 h-3" />
            {session.viewer_count}
          </span>
          <span>{timeAgo(session.started_at)}</span>
        </span>
      </footer>
    </Link>
  );
}

function EmptyState({ onStart }: { onStart: () => void }) {
  return (
    <div className="bg-white border border-dashed border-slate-200 rounded-2xl p-10 text-center">
      <Video className="w-10 h-10 mx-auto mb-3 text-slate-300" />
      <p className="text-sm font-medium text-slate-600">No live sessions right now.</p>
      <p className="text-xs text-slate-400 mt-1 mb-4">Be the first to go live for your class.</p>
      <button
        onClick={onStart}
        className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 text-white text-sm font-semibold px-4 py-2 rounded-lg"
      >
        <Plus className="w-4 h-4" />
        Start a live session
      </button>
    </div>
  );
}

// Shown only when the org has no timetable and no past sessions — the
// "brand-new school" path. Each step links to the page that gets it done
// so a non-technical teacher can hit it top-to-bottom without guessing.
function GettingStarted({ onStart }: { onStart: () => void }) {
  const steps: { icon: React.ReactNode; title: string; body: string; href?: string; cta: string; action?: () => void }[] = [
    {
      icon: <GraduationCap className="w-5 h-5 text-brand-500" />,
      title: "Create a class",
      body: "Add your first class roster — Grade 10A, JSS 2 Maths, etc. You can bulk-import from CSV.",
      href: "/dashboard/modules/school/classes",
      cta: "Go to classes",
    },
    {
      icon: <Users className="w-5 h-5 text-emerald-500" />,
      title: "Add students",
      body: "Enrol students and send them login details. They'll join live sessions with their own account.",
      href: "/dashboard/modules/school/students",
      cta: "Go to students",
    },
    {
      icon: <Calendar className="w-5 h-5 text-amber-500" />,
      title: "Schedule a lesson",
      body: "Add a timetable slot. You'll get a one-tap 'Go Live' button at the start of each slot.",
      href: "/dashboard/modules/school/timetable",
      cta: "Open timetable",
    },
    {
      icon: <Radio className="w-5 h-5 text-rose-500" />,
      title: "Go live",
      body: "Start your first session. Students join from the live page — no extra tools to install.",
      cta: "Start a session",
      action: onStart,
    },
  ];

  return (
    <div className="bg-gradient-to-br from-brand-50 via-white to-rose-50 border border-brand-100 rounded-2xl p-6 lg:p-8">
      <div className="flex items-start gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-brand-500 flex items-center justify-center text-white">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-lg font-black text-slate-900">
            Welcome to Live Classes
          </h2>
          <p className="text-sm text-slate-600 mt-0.5">
            Four quick steps get your school streaming. You only need to do this once.
          </p>
        </div>
      </div>

      <ol className="space-y-3">
        {steps.map((step, idx) => (
          <li
            key={step.title}
            className="bg-white border border-slate-200 rounded-xl p-4 flex items-start gap-3"
          >
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-slate-100 text-slate-600 text-xs font-black flex items-center justify-center">
              {idx + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                {step.icon}
                <h3 className="text-sm font-bold text-slate-900">{step.title}</h3>
              </div>
              <p className="text-xs text-slate-500 mt-1">{step.body}</p>
            </div>
            {step.href ? (
              <Link
                href={step.href}
                className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700 whitespace-nowrap"
              >
                {step.cta}
                <ArrowRight className="w-3 h-3" />
              </Link>
            ) : (
              <button
                onClick={step.action}
                className="flex-shrink-0 inline-flex items-center gap-1 text-xs font-semibold bg-rose-600 hover:bg-rose-700 text-white px-3 py-1.5 rounded-lg whitespace-nowrap"
              >
                <Plus className="w-3 h-3" />
                {step.cta}
              </button>
            )}
          </li>
        ))}
      </ol>

      <p className="text-[11px] text-slate-400 mt-4 flex items-center gap-1">
        <ListChecks className="w-3 h-3" />
        This panel disappears automatically once you've set up a timetable slot or run your first session.
      </p>
    </div>
  );
}

function StartModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [classId, setClassId] = useState<string>("");
  const [classes, setClasses] = useState<ClassOption[]>([]);
  const start = useStartLive();

  useEffect(() => {
    // Host can optionally scope the session to one class. The backend
    // enforces the roster gate; leaving blank = open to the whole org.
    schoolApi.classes
      .list()
      // /school/classes returns { items, total, … }, not a bare array — pull items
      // (guard for a plain-array shape too) so classes stays an array for .map.
      .then((data: any) => setClasses(Array.isArray(data) ? data : (data?.items ?? [])))
      .catch(() => setClasses([]));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error("Give the session a title first.");
      return;
    }
    const s = await start.mutateAsync({
      title: title.trim(),
      description: description.trim() || undefined,
      class_id: classId || undefined,
    });
    // Send the host straight into their own room.
    window.location.href = `/dashboard/modules/school/cbt/live/${s.id}`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 px-4">
      <form
        onSubmit={submit}
        className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4"
      >
        <header className="flex items-center gap-2">
          <Radio className="w-5 h-5 text-rose-500" />
          <h2 className="text-lg font-bold text-slate-800">Start a live session</h2>
        </header>
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40"
            placeholder="e.g. Year 10 Mathematics — Quadratics Recap"
            autoFocus
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1">
            Description <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-slate-600 mb-1">
            Class <span className="text-slate-400 font-normal">(optional — restricts to enrolled students)</span>
          </label>
          <select
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-rose-500/40"
          >
            <option value="">Open to the whole school</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={start.isPending}
            className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg"
          >
            {start.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Radio className="w-4 h-4" />}
            Go live
          </button>
        </div>
      </form>
    </div>
  );
}
