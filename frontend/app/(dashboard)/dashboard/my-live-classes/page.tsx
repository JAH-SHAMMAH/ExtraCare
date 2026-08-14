"use client";

import { useState } from "react";
import { useLiveSessions, useLiveRecordings } from "@/hooks/useLive";
import { formatDate } from "@/lib/utils";
import { Radio, Users, PlayCircle, Clock, Loader2 } from "lucide-react";
import type { LiveSession } from "@/types";

/**
 * Student-only My Live Classes page
 *
 * Independent of the admin /cbt/live tree. Gated via CORE_NAV roleOnly: "student"
 * with no permission check — fully roster-scoped server-side via
 * list_sessions() which filters via _is_user_authorised_for_session().
 *
 * Students can:
 * - View active sessions for their class
 * - Join active sessions (WebRTC)
 * - View attendance history
 * - Replay recorded past sessions
 *
 * Students cannot:
 * - Create/manage sessions (requires school:cbt:manage)
 * - Access sessions outside their roster
 */

export default function MyLiveClassesPage() {
  const { data: activeSessions = [], isLoading } = useLiveSessions(true);
  const { data: allSessions = [] } = useLiveSessions(false);
  const [playbackSession, setPlaybackSession] = useState<LiveSession | null>(null);

  const pastWithRecording = allSessions.filter(
    (s) => !s.is_active && s.has_recording
  );

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="mb-8">
        <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <span>Education</span>
          <span>/</span>
          <span className="text-brand-600 font-semibold">My Live Classes</span>
        </nav>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight flex items-center gap-2">
          <Radio className="w-6 h-6 text-rose-500" />
          Live Classes
        </h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Join a live session with your teacher or watch recorded classes.
        </p>
      </div>

      {/* Active Sessions */}
      <section>
        <h2 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
          <Radio className="w-4 h-4 text-rose-500" />
          Active sessions
        </h2>

        {isLoading ? (
          <div className="flex items-center justify-center py-10 text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin" />
          </div>
        ) : activeSessions.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 flex flex-col items-center justify-center py-12 text-slate-400">
            <Radio size={40} className="mb-3 opacity-40" />
            <p className="font-semibold">No live sessions right now</p>
            <p className="text-sm mt-1">Check back when your teacher starts one.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {activeSessions.map((session) => (
              <StudentSessionCard
                key={session.id}
                session={session}
                canJoin={true}
              />
            ))}
          </div>
        )}
      </section>

      {/* Recorded Sessions */}
      {pastWithRecording.length > 0 && (
        <section className="pt-4 border-t border-slate-200">
          <h2 className="text-sm font-bold text-slate-700 mb-3 flex items-center gap-2">
            <PlayCircle className="w-4 h-4 text-brand-500" />
            Recorded sessions
          </h2>
          <div className="space-y-3">
            {pastWithRecording.map((session) => (
              <StudentSessionCard
                key={session.id}
                session={session}
                canJoin={false}
                onPlayRecording={() => setPlaybackSession(session)}
              />
            ))}
          </div>
        </section>
      )}

      {/* Playback Modal (if needed) */}
      {playbackSession && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-xl max-w-2xl w-full max-h-[80vh] overflow-auto">
            <div className="p-6 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-bold text-slate-900">{playbackSession.title}</h3>
              <button
                onClick={() => setPlaybackSession(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <div className="p-6">
              <RecordingPlayer session={playbackSession} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function StudentSessionCard({
  session,
  canJoin,
  onPlayRecording,
}: {
  session: LiveSession;
  canJoin?: boolean;
  onPlayRecording?: () => void;
}) {
  const now = new Date();
  const startTime = session.started_at ? new Date(session.started_at) : null;
  const endTime = session.ended_at ? new Date(session.ended_at) : null;
  const isLive = session.is_active && startTime;
  const duration = startTime && endTime
    ? Math.round((endTime.getTime() - startTime.getTime()) / 60000)
    : null;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="text-sm font-bold text-slate-900">{session.title}</h3>
          {session.class_id && (
            <p className="text-xs text-slate-500 mt-1">
              Class session
            </p>
          )}
        </div>
        {isLive && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-600 bg-rose-50 border border-rose-200 rounded-full px-2.5 py-1">
            <span className="w-2 h-2 rounded-full bg-rose-600 animate-pulse" />
            Live
          </span>
        )}
      </div>

      <div className="space-y-1.5 mb-4 text-xs text-slate-500">
        {startTime && (
          <div className="flex items-center gap-1.5">
            <Clock size={12} />
            {formatDate(session.started_at || "")}
          </div>
        )}
        {session.viewer_count !== undefined && (
          <div className="flex items-center gap-1.5">
            <Users size={12} />
            {session.viewer_count} watching
          </div>
        )}
        {duration && !isLive && (
          <div className="flex items-center gap-1.5">
            <Clock size={12} />
            {duration} min
          </div>
        )}
      </div>

      <div className="pt-3 border-t border-slate-100">
        {canJoin && isLive ? (
          <button className="w-full text-xs font-semibold text-rose-600 hover:text-rose-700 py-2">
            Join Now →
          </button>
        ) : session.has_recording && onPlayRecording ? (
          <button
            onClick={onPlayRecording}
            className="w-full text-xs font-semibold text-brand-600 hover:text-brand-700 py-2"
          >
            Play Recording →
          </button>
        ) : (
          <div className="text-xs text-slate-400 text-center py-2">
            {isLive ? "Session closed" : "No recording available"}
          </div>
        )}
      </div>
    </div>
  );
}

function RecordingPlayer({ session }: { session: LiveSession }) {
  const { data: recordings = [] } = useLiveRecordings(session.id);

  if (recordings.length === 0) {
    return (
      <div className="text-center py-8 text-slate-400">
        <p>Recording not yet available</p>
      </div>
    );
  }

  const recording = recordings[0];

  return (
    <div className="space-y-4">
      {recording.file_url ? (
        <video
          src={recording.file_url}
          controls
          className="w-full rounded-lg bg-black"
          autoPlay
        />
      ) : (
        <div className="bg-slate-100 rounded-lg aspect-video flex items-center justify-center text-slate-400">
          Video unavailable
        </div>
      )}
      <div className="text-xs text-slate-500">
        <p>
          Duration: {recording.duration_seconds ? `${Math.round(recording.duration_seconds / 60)} min` : "unknown"}
        </p>
      </div>
    </div>
  );
}
