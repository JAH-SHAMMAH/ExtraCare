"use client";

import { Loader2, WifiOff } from "lucide-react";

// Full-screen translucent overlay rendered when the signaling socket is
// reconnecting. Keeps the video visible underneath (WebRTC is still alive)
// but makes clear to the user that controls are temporarily in limbo.
export function ReconnectOverlay({
  attempts,
  givenUp,
}: {
  attempts: number;
  givenUp: boolean;
}) {
  if (attempts <= 0 && !givenUp) return null;

  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-slate-950/75 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl px-6 py-5 max-w-sm text-center shadow-xl">
        {givenUp ? (
          <>
            <WifiOff className="w-8 h-8 text-rose-400 mx-auto mb-3" />
            <p className="text-sm font-bold text-white">We couldn't reconnect.</p>
            <p className="text-xs text-slate-400 mt-1">
              Check your network and refresh the page to rejoin.
            </p>
          </>
        ) : (
          <>
            <Loader2 className="w-8 h-8 text-amber-300 mx-auto mb-3 animate-spin" />
            <p className="text-sm font-bold text-white">Reconnecting…</p>
            <p className="text-xs text-slate-400 mt-1">
              Attempt {attempts} — your class is still running, just tightening
              the connection.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
