"use client";

import { Hand, Mic, MicOff, UserMinus, Volume2, X } from "lucide-react";

export type ParticipantInfo = {
  user_id: string;
  name: string;
  handRaised: boolean;
  muted: boolean;
  speaking?: boolean;
};

// Hand-raised participants float to the top — teachers glance here to decide
// who to call on.
export function sortParticipants(list: ParticipantInfo[]): ParticipantInfo[] {
  return [...list].sort((a, b) => {
    if (a.handRaised !== b.handRaised) return a.handRaised ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
}

export interface ParticipantsPanelProps {
  participants: ParticipantInfo[];
  onMute: (userId: string, mute: boolean) => void;
  onKick: (userId: string) => void;
  onMuteAll: () => void;
  onUnmuteAll: () => void;
  onClose?: () => void;
  isMobile?: boolean;
}

export function ParticipantsPanel({
  participants,
  onMute,
  onKick,
  onMuteAll,
  onUnmuteAll,
  onClose,
  isMobile,
}: ParticipantsPanelProps) {
  const sorted = sortParticipants(participants);
  const handsUp = sorted.filter((p) => p.handRaised).length;

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between p-4 border-b border-slate-800">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wide text-slate-200">
            Participants ({sorted.length})
          </h2>
          {handsUp > 0 && (
            <p className="text-[11px] text-amber-400 mt-0.5 flex items-center gap-1">
              <Hand className="w-3 h-3" />
              {handsUp} hand{handsUp > 1 ? "s" : ""} raised
            </p>
          )}
        </div>
        {isMobile && onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-800 text-slate-400"
            aria-label="Close participants"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </header>

      {sorted.length > 0 && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-800 bg-slate-900/60">
          <button
            onClick={onMuteAll}
            className="flex-1 inline-flex items-center justify-center gap-1 text-[11px] font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 py-1.5 rounded"
          >
            <MicOff className="w-3.5 h-3.5" />
            Mute all
          </button>
          <button
            onClick={onUnmuteAll}
            className="flex-1 inline-flex items-center justify-center gap-1 text-[11px] font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 py-1.5 rounded"
          >
            <Mic className="w-3.5 h-3.5" />
            Unmute all
          </button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3">
        {sorted.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-6">
            Waiting for students to join…
          </p>
        ) : (
          <ul className="space-y-2">
            {sorted.map((v) => (
              <ParticipantRow key={v.user_id} p={v} onMute={onMute} onKick={onKick} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ParticipantRow({
  p,
  onMute,
  onKick,
}: {
  p: ParticipantInfo;
  onMute: (id: string, mute: boolean) => void;
  onKick: (id: string) => void;
}) {
  const initials = (p.name || "?")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");

  return (
    <li
      className={`flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 border transition-colors ${
        p.handRaised
          ? "bg-amber-950/40 border-amber-700/50"
          : p.speaking
          ? "bg-emerald-950/40 border-emerald-700/50"
          : "bg-slate-900 border-slate-800"
      }`}
    >
      <div className="min-w-0 flex items-center gap-2">
        <span
          className={`relative w-7 h-7 flex-shrink-0 rounded-full bg-slate-700 text-[10px] font-bold text-slate-200 flex items-center justify-center ${
            p.speaking ? "ring-2 ring-emerald-400" : ""
          }`}
        >
          {initials || "·"}
          {p.speaking && (
            <span className="absolute -right-0.5 -bottom-0.5 bg-emerald-500 rounded-full p-0.5">
              <Volume2 className="w-2 h-2 text-white" />
            </span>
          )}
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-1">
            {p.handRaised && <Hand className="w-3 h-3 text-amber-400 flex-shrink-0" />}
            <span className="text-xs font-medium text-slate-200 truncate">{p.name}</span>
          </div>
          {p.handRaised && (
            <p className="text-[10px] text-amber-400 mt-0.5">Wants to speak</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <button
          onClick={() => onMute(p.user_id, !p.muted)}
          title={p.muted ? "Unmute" : "Mute"}
          className={`p-1 rounded hover:bg-slate-800 ${
            p.muted ? "text-rose-400" : "text-slate-400"
          }`}
        >
          {p.muted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
        </button>
        <button
          onClick={() => onKick(p.user_id)}
          title="Remove participant"
          className="p-1 rounded text-slate-400 hover:bg-slate-800 hover:text-rose-400"
        >
          <UserMinus className="w-3.5 h-3.5" />
        </button>
      </div>
    </li>
  );
}
