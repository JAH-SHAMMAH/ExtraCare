"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Radio, Loader2, LogOut, Users, AlertCircle, Circle, Square,
  Hand, BarChart3, X, Menu,
} from "lucide-react";
import { toast } from "sonner";
import { useLiveSession, useEndLive, useUploadRecording, useLiveAnalytics } from "@/hooks/useLive";
import { useAuthStore } from "@/lib/store";
import { liveApi } from "@/lib/api";
import { resolveMediaUrl } from "@/lib/utils";
import {
  paramsForTier,
  tierForViewerCount,
  type QualityTier,
} from "@/lib/live/encodingTiers";
import {
  createAdaptiveState,
  sampleFromStats,
  updateTierWithHysteresis,
  type AdaptiveState,
} from "@/lib/live/adaptiveBitrate";
import {
  applyEncodingParams,
  createIceRestartOffer,
  shouldAttemptIceRestart,
} from "@/lib/live/rtcHelpers";
import { createReconnectController, type ReconnectController } from "@/lib/live/reconnect";
import { createSpeakingDetector, type SpeakingDetector } from "@/lib/live/speakingDetector";
import { ConnectionBadge } from "@/components/live/ConnectionBadge";
import { ReconnectOverlay } from "@/components/live/ReconnectOverlay";
import { ParticipantsPanel, type ParticipantInfo } from "@/components/live/ParticipantsPanel";

// STUN-only fallback used only if /live/ice-config fails. The backend
// endpoint returns configured TURN servers (with ephemeral creds when
// TURN_SECRET is set) — which is what schools on strict NAT actually need.
const FALLBACK_RTC_CONFIG: RTCConfiguration = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

type Role = "host" | "viewer" | null;

type ViewerInfo = {
  user_id: string;
  name: string;
  handRaised: boolean;
  muted: boolean;
};

export default function LiveRoomPage() {
  const params = useParams<{ session_id: string }>();
  const sessionId = params.session_id;
  const router = useRouter();
  const { user, org } = useAuthStore();

  const { data: session, isLoading, error } = useLiveSession(sessionId);
  const endSession = useEndLive();
  const uploadRec = useUploadRecording(sessionId);

  const [role, setRole] = useState<Role>(null);
  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState<string>("Connecting…");
  const [viewers, setViewers] = useState<Record<string, ViewerInfo>>({});
  const [handRaised, setHandRaised] = useState(false);
  const [recording, setRecording] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);

  const localVideoRef = useRef<HTMLVideoElement>(null);
  const remoteVideoRef = useRef<HTMLVideoElement>(null);

  // Keep WebRTC + WS state in refs so re-renders don't rebuild them.
  const wsRef = useRef<WebSocket | null>(null);
  const localStreamRef = useRef<MediaStream | null>(null);
  const peersRef = useRef<Map<string, RTCPeerConnection>>(new Map());
  const pendingCandidatesRef = useRef<Map<string, RTCIceCandidateInit[]>>(new Map());
  const rtcConfigRef = useRef<RTCConfiguration>(FALLBACK_RTC_CONFIG);

  // Recording state — chunks accumulate in-memory then upload as one blob.
  // For long sessions we could stream in chunks, but that's a later win.
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingStartRef = useRef<number>(0);

  // Adaptive bitrate: per-peer sampler state + polling interval.
  const adaptiveStatesRef = useRef<Map<string, AdaptiveState>>(new Map());
  const statsIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reconnect: controller survives across WS lifetimes; a teardown flag blocks
  // auto-reconnect when the user explicitly leaves.
  const reconnectRef = useRef<ReconnectController | null>(null);
  const teardownFlagRef = useRef<boolean>(false);

  // Track current quality tier for display (debugging / future UX).
  const [qualityTier, setQualityTier] = useState<QualityTier | null>(null);

  // UX surfaces: reconnect attempts drive the overlay; speaking drives the
  // self-video ring and the participant avatar pulse.
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [reconnectGivenUp, setReconnectGivenUp] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [showParticipants, setShowParticipants] = useState(false);
  const [recordingElapsed, setRecordingElapsed] = useState(0);
  const speakingDetectorRef = useRef<SpeakingDetector | null>(null);

  const isHost = !!session && !!user && session.host_user_id === user.id;

  useEffect(() => {
    if (!session || !user) return;
    setRole(isHost ? "host" : "viewer");
    teardownFlagRef.current = false;

    let cancelled = false;

    const run = async () => {
      try {
        try {
          const cfg = await liveApi.iceConfig();
          if (cfg?.iceServers?.length) {
            rtcConfigRef.current = { iceServers: cfg.iceServers };
          }
        } catch {
          // STUN-only fallback is already set.
        }
        if (isHost) {
          setStatus("Requesting camera access…");
          const stream = await navigator.mediaDevices.getUserMedia({
            video: true,
            audio: true,
          });
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop());
            return;
          }
          localStreamRef.current = stream;
          if (localVideoRef.current) localVideoRef.current.srcObject = stream;
          // Pulse the self-video ring when the host speaks — lightweight
          // signal that audio is reaching the students.
          speakingDetectorRef.current = createSpeakingDetector(stream, {
            onChange: (s) => setSpeaking(s),
          });
        }
        connectWs();
      } catch (err: any) {
        if (err?.name === "NotAllowedError") {
          setStatus("Camera/microphone permission denied.");
        } else {
          setStatus(err?.message || "Failed to start.");
        }
      }
    };

    run();

    return () => {
      cancelled = true;
      stopRecorder();
      teardown();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id, user?.id, isHost]);

  const connectWs = () => {
    if (!reconnectRef.current) {
      reconnectRef.current = createReconnectController(() => connectWs(), {
        maxAttempts: 8,
        baseDelayMs: 500,
        maxDelayMs: 15_000,
        onAttempt: (n, d) => {
          setReconnectAttempts(n);
          setStatus(`Reconnecting (attempt ${n}) in ${Math.round(d / 1000)}s…`);
        },
        onGiveUp: () => {
          setReconnectGivenUp(true);
          setStatus("Could not reconnect. Please refresh the page.");
        },
      });
    }

    const ws = new WebSocket(liveApi.wsUrl(sessionId));
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectRef.current?.reset();
      setReconnectAttempts(0);
      setReconnectGivenUp(false);
      setConnected(true);
      setStatus(isHost ? "Live — waiting for viewers" : "Connected — waiting for host offer");
    };

    ws.onclose = () => {
      setConnected(false);
      if (teardownFlagRef.current) return;
      setStatus("Signal dropped — reconnecting…");
      reconnectRef.current?.schedule();
    };

    ws.onerror = () => setStatus("Signaling connection error.");

    ws.onmessage = async (raw) => {
      const data = safeParse(raw.data);
      if (!data) return;

      if (data.event === "error") {
        toast.error(data.detail || "Live error");
        setStatus(data.detail === "host_offline" ? "Host is offline." : "Error.");
        return;
      }
      if (data.event === "connected") return;
      if (data.event === "host_left") {
        setStatus("The host ended the session.");
        teardown();
        return;
      }
      if (data.event === "viewer_joined") {
        if (isHost) {
          setViewers((v) => ({
            ...v,
            [data.user_id]: {
              user_id: data.user_id,
              name: data.name || "Viewer",
              handRaised: false,
              muted: false,
            },
          }));
          await createOfferForViewer(data.user_id);
        }
        return;
      }

      const from = data.from as string | undefined;
      if (!from) return;

      if (data.type === "offer") {
        await handleOffer(from, data.sdp);
      } else if (data.type === "answer") {
        const pc = peersRef.current.get(from);
        if (pc) {
          await pc.setRemoteDescription({ type: "answer", sdp: data.sdp });
          await flushPendingCandidates(from);
        }
      } else if (data.type === "candidate") {
        await handleCandidate(from, data.candidate);
      } else if (data.type === "bye") {
        const pc = peersRef.current.get(from);
        if (pc) {
          pc.close();
          peersRef.current.delete(from);
        }
        adaptiveStatesRef.current.delete(from);
        pendingCandidatesRef.current.delete(from);
        setViewers((v) => {
          const next = { ...v };
          delete next[from];
          return next;
        });
      } else if (data.type === "hand_raise" && isHost) {
        // Host-only: update the viewer list with the raised flag.
        const name = viewersRef.current[from]?.name || "A viewer";
        setViewers((prev) => ({
          ...prev,
          [from]: {
            ...(prev[from] || { user_id: from, name, muted: false }),
            handRaised: !!data.raised,
          },
        }));
        if (data.raised) toast.info(`${name} raised their hand`);
      } else if (data.type === "mute" && !isHost) {
        // Viewer-only: host requested us to mute. Cut our mic locally.
        toggleLocalAudio(false);
        toast.warning("Host muted your microphone.");
      } else if (data.type === "unmute" && !isHost) {
        toggleLocalAudio(true);
        toast.info("Host un-muted your microphone.");
      } else if (data.type === "kick" && !isHost) {
        toast.error("You've been removed from the session.");
        teardown();
        router.push("/dashboard/modules/school/cbt/live");
      }
    };
  };

  // Store current viewers in a ref too so the WS handler can read without re-subscribing.
  const viewersRef = useRef<Record<string, ViewerInfo>>({});
  useEffect(() => {
    viewersRef.current = viewers;
  }, [viewers]);

  // Host-only: every 3s, sample each peer's stats and adjust its encoding tier.
  // The hysteresis in updateTierWithHysteresis prevents thrashing on blips.
  useEffect(() => {
    if (!isHost || !connected) return;
    const handle = setInterval(async () => {
      const peers = peersRef.current;
      let displayTier: QualityTier | null = null;
      for (const [viewerId, pc] of peers.entries()) {
        if (pc.connectionState === "closed" || pc.connectionState === "failed") continue;
        const state = adaptiveStatesRef.current.get(viewerId);
        if (!state) continue;
        try {
          const report = await pc.getStats();
          const sample = sampleFromStats(report, state);
          if (!sample) continue;
          const prev = state.currentTier;
          const next = updateTierWithHysteresis(state, sample);
          if (next !== prev) {
            await applyEncodingParams(pc, paramsForTier(next));
          }
          if (!displayTier || tierIsLower(next, displayTier)) displayTier = next;
        } catch {
          // getStats can reject during negotiation — try again next tick.
        }
      }
      if (displayTier) setQualityTier(displayTier);
    }, 3_000);
    statsIntervalRef.current = handle;
    return () => {
      clearInterval(handle);
      statsIntervalRef.current = null;
    };
  }, [isHost, connected]);

  // Tick a user-visible timer while recording so teachers see how long
  // they've been capturing (and can stop before the quota bites).
  useEffect(() => {
    if (!recording) {
      setRecordingElapsed(0);
      return;
    }
    const id = setInterval(() => {
      setRecordingElapsed(Math.floor((Date.now() - recordingStartRef.current) / 1000));
    }, 1_000);
    return () => clearInterval(id);
  }, [recording]);

  // Host-only: when the viewer count crosses a tier boundary, pull all peers
  // down to at least the new baseline. Never upgrade here — adaptive loop handles that.
  useEffect(() => {
    if (!isHost) return;
    const count = Object.keys(viewers).length;
    if (count === 0) return;
    const baselineTier = tierForViewerCount(count);
    const baselineRank = tierRankForDisplay(baselineTier);
    for (const [viewerId, pc] of peersRef.current.entries()) {
      const state = adaptiveStatesRef.current.get(viewerId);
      if (!state) continue;
      if (tierRankForDisplay(state.currentTier) > baselineRank) {
        state.currentTier = baselineTier;
        applyEncodingParams(pc, paramsForTier(baselineTier)).catch(() => {});
      }
    }
  }, [isHost, viewers]);

  const toggleLocalAudio = (enabled: boolean) => {
    const s = localStreamRef.current;
    s?.getAudioTracks().forEach((t) => (t.enabled = enabled));
  };

  // ── Host: fan out one offer per connecting viewer ────────────────────────

  const createOfferForViewer = async (viewerId: string) => {
    // Close any stale peer for this viewer (handles reconnects).
    const existing = peersRef.current.get(viewerId);
    if (existing) {
      existing.close();
      peersRef.current.delete(viewerId);
    }

    const pc = new RTCPeerConnection(rtcConfigRef.current);
    peersRef.current.set(viewerId, pc);

    const stream = localStreamRef.current;
    if (stream) stream.getTracks().forEach((t) => pc.addTrack(t, stream));

    pc.onicecandidate = (e) => {
      if (e.candidate) send({ type: "candidate", target: viewerId, candidate: e.candidate });
    };

    pc.oniceconnectionstatechange = async () => {
      if (shouldAttemptIceRestart(pc.iceConnectionState)) {
        const offer = await createIceRestartOffer(pc);
        if (offer?.sdp) send({ type: "offer", target: viewerId, sdp: offer.sdp });
      }
    };

    // Initial tier based on current viewer count — new large classes start in
    // low/audio mode so we don't spike host CPU while mid-session.
    const currentCount = peersRef.current.size;
    const initialTier = tierForViewerCount(currentCount);
    adaptiveStatesRef.current.set(viewerId, createAdaptiveState(initialTier));

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    send({ type: "offer", target: viewerId, sdp: offer.sdp });

    // Apply encoding *after* setLocalDescription so senders are wired up.
    await applyEncodingParams(pc, paramsForTier(initialTier));
  };

  // ── Viewer: accept offer, publish answer ─────────────────────────────────

  const handleOffer = async (hostId: string, sdp: string) => {
    let pc = peersRef.current.get(hostId);
    if (!pc) {
      pc = new RTCPeerConnection(rtcConfigRef.current);
      peersRef.current.set(hostId, pc);
      pc.ontrack = (e) => {
        if (remoteVideoRef.current) {
          remoteVideoRef.current.srcObject = e.streams[0];
          setStatus("Receiving host stream.");
        }
        // Viewer speaking indicator — teacher talking → ring lights up.
        speakingDetectorRef.current?.stop();
        speakingDetectorRef.current = createSpeakingDetector(e.streams[0], {
          onChange: (s) => setSpeaking(s),
        });
      };
      pc.onicecandidate = (e) => {
        if (e.candidate) send({ type: "candidate", target: hostId, candidate: e.candidate });
      };
      // Viewer reacts to ICE drops by closing — host will re-offer on next
      // viewer_joined or via its own ICE restart path.
      pc.oniceconnectionstatechange = () => {
        if (pc && shouldAttemptIceRestart(pc.iceConnectionState)) {
          setStatus("Reconnecting to host…");
        }
      };
    }
    await pc.setRemoteDescription({ type: "offer", sdp });
    await flushPendingCandidates(hostId);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    send({ type: "answer", target: hostId, sdp: answer.sdp });
  };

  const handleCandidate = async (from: string, candidate: RTCIceCandidateInit) => {
    const pc = peersRef.current.get(from);
    if (!pc || !pc.remoteDescription) {
      const list = pendingCandidatesRef.current.get(from) || [];
      list.push(candidate);
      pendingCandidatesRef.current.set(from, list);
      return;
    }
    try {
      await pc.addIceCandidate(candidate);
    } catch {
      // stale candidates are non-fatal
    }
  };

  const flushPendingCandidates = async (from: string) => {
    const list = pendingCandidatesRef.current.get(from);
    if (!list) return;
    const pc = peersRef.current.get(from);
    if (!pc) return;
    for (const c of list) {
      try {
        await pc.addIceCandidate(c);
      } catch {
        // ignore
      }
    }
    pendingCandidatesRef.current.delete(from);
  };

  const send = (payload: object) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(payload));
  };

  // ── Recording (host only) ────────────────────────────────────────────────

  const pickMime = () => {
    // Prefer VP9; fall back through the usual chain so Safari still records.
    const candidates = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
      "video/mp4",
    ];
    for (const m of candidates) {
      // @ts-ignore — isTypeSupported exists at runtime
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported?.(m)) return m;
    }
    return "";
  };

  const startRecorder = () => {
    const stream = localStreamRef.current;
    if (!stream) {
      toast.error("No stream to record yet.");
      return;
    }
    const mime = pickMime();
    try {
      const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recordedChunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) recordedChunksRef.current.push(e.data);
      };
      rec.onstop = async () => {
        const chunks = recordedChunksRef.current;
        recordedChunksRef.current = [];
        if (!chunks.length) return;
        const blob = new Blob(chunks, { type: mime || "video/webm" });
        const duration = Math.max(1, Math.round((Date.now() - recordingStartRef.current) / 1000));
        try {
          await uploadRec.mutateAsync({ blob, duration_seconds: duration });
          toast.success("Recording saved.");
        } catch {
          // toast handled by the hook
        }
      };
      recordingStartRef.current = Date.now();
      // 1s timeslice so chunks arrive periodically — safer if the tab crashes.
      rec.start(1000);
      mediaRecorderRef.current = rec;
      setRecording(true);
    } catch (err: any) {
      toast.error(err?.message || "Recording not supported here.");
    }
  };

  const stopRecorder = () => {
    const rec = mediaRecorderRef.current;
    if (rec && rec.state !== "inactive") {
      try {
        rec.stop();
      } catch {
        // ignore
      }
    }
    mediaRecorderRef.current = null;
    setRecording(false);
  };

  // ── In-session controls ──────────────────────────────────────────────────

  const toggleHandRaise = () => {
    const next = !handRaised;
    setHandRaised(next);
    send({ type: "hand_raise", target: "host", raised: next });
  };

  const muteViewer = (viewerId: string, mute: boolean) => {
    send({ type: mute ? "mute" : "unmute", target: viewerId });
    setViewers((v) => ({
      ...v,
      [viewerId]: { ...v[viewerId], muted: mute },
    }));
  };

  const muteAll = () => {
    send({ type: "mute", target: "all" });
    setViewers((v) => {
      const next: Record<string, ViewerInfo> = {};
      for (const [k, info] of Object.entries(v)) next[k] = { ...info, muted: true };
      return next;
    });
    toast.success("Muted every participant.");
  };

  const unmuteAll = () => {
    send({ type: "unmute", target: "all" });
    setViewers((v) => {
      const next: Record<string, ViewerInfo> = {};
      for (const [k, info] of Object.entries(v)) next[k] = { ...info, muted: false };
      return next;
    });
    toast.success("Un-muted every participant.");
  };

  const kickViewer = (viewerId: string) => {
    if (!confirm("Remove this viewer from the session?")) return;
    send({ type: "kick", target: viewerId });
    // Don't wait for their bye — drop the peer now.
    const pc = peersRef.current.get(viewerId);
    pc?.close();
    peersRef.current.delete(viewerId);
    adaptiveStatesRef.current.delete(viewerId);
    pendingCandidatesRef.current.delete(viewerId);
    setViewers((v) => {
      const next = { ...v };
      delete next[viewerId];
      return next;
    });
  };

  const teardown = () => {
    teardownFlagRef.current = true;
    reconnectRef.current?.cancel();
    reconnectRef.current = null;
    speakingDetectorRef.current?.stop();
    speakingDetectorRef.current = null;
    if (statsIntervalRef.current) {
      clearInterval(statsIntervalRef.current);
      statsIntervalRef.current = null;
    }
    adaptiveStatesRef.current.clear();
    wsRef.current?.close();
    wsRef.current = null;
    peersRef.current.forEach((pc) => pc.close());
    peersRef.current.clear();
    pendingCandidatesRef.current.clear();
    localStreamRef.current?.getTracks().forEach((t) => t.stop());
    localStreamRef.current = null;
    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
  };

  const leave = async () => {
    if (isHost) {
      if (!confirm("End the session for everyone?")) return;
      stopRecorder();
      // Give the upload a head-start; hook invalidates caches on success.
      await endSession.mutateAsync(sessionId);
    }
    teardown();
    router.push("/dashboard/modules/school/cbt/live");
  };

  const viewerList = Object.values(viewers);
  const viewerCount = isHost ? viewerList.length : (session?.viewer_count ?? 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
        <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="p-8">
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center">
          <AlertCircle className="w-8 h-8 text-rose-500 mx-auto mb-2" />
          <p className="text-sm font-semibold text-rose-700">This session is not available.</p>
          <Link
            href="/dashboard/modules/school/cbt/live"
            className="text-xs text-rose-600 underline mt-2 inline-block"
          >
            Back to live sessions
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] bg-slate-900 text-white flex flex-col">
      <header className="flex items-center justify-between gap-2 px-4 sm:px-6 py-3 border-b border-slate-800">
        <div className="flex items-center gap-3 min-w-0">
          {org?.logo_url ? (
            <img
              src={resolveMediaUrl(org.logo_url)}
              alt={org.name}
              className="w-8 h-8 rounded-lg object-cover flex-shrink-0 bg-slate-800"
            />
          ) : (
            <Radio className={`w-5 h-5 flex-shrink-0 ${connected ? "text-rose-400 animate-pulse" : "text-slate-500"}`} />
          )}
          <div className="min-w-0">
            <h1 className="text-sm font-bold truncate">{session.title}</h1>
            <p className="text-[11px] text-slate-400 truncate">
              {org?.name ? `${org.name} · ` : ""}
              {session.host_name} · {role === "host" ? "You are the host" : "Viewing"}
            </p>
          </div>
          {recording && (
            <span className="hidden sm:inline-flex items-center gap-1 bg-rose-600/90 text-white text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded-full">
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
              REC {fmtMmSs(recordingElapsed)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ConnectionBadge
            connected={connected}
            reconnectAttempts={reconnectAttempts}
            tier={qualityTier}
          />
          <span className="hidden sm:inline-flex items-center gap-1 text-xs text-slate-400">
            <Users className="w-3.5 h-3.5" />
            {viewerCount}
          </span>

          {isHost && (
            <>
              <button
                onClick={recording ? stopRecorder : startRecorder}
                className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg ${
                  recording
                    ? "bg-slate-700 hover:bg-slate-600"
                    : "bg-emerald-600 hover:bg-emerald-700"
                }`}
              >
                {recording ? <Square className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />}
                <span className="hidden sm:inline">{recording ? "Stop recording" : "Record"}</span>
              </button>
              <button
                onClick={() => setShowAnalytics(true)}
                className="hidden sm:inline-flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold px-3 py-1.5 rounded-lg"
              >
                <BarChart3 className="w-3.5 h-3.5" />
                Analytics
              </button>
              <button
                onClick={() => setShowParticipants(true)}
                className="lg:hidden inline-flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-semibold px-3 py-1.5 rounded-lg"
                aria-label="Open participants"
              >
                <Menu className="w-3.5 h-3.5" />
                <span className="hidden xs:inline">{viewerList.length}</span>
              </button>
            </>
          )}

          {!isHost && (
            <button
              onClick={toggleHandRaise}
              className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg ${
                handRaised ? "bg-amber-500 hover:bg-amber-600" : "bg-slate-800 hover:bg-slate-700"
              }`}
            >
              <Hand className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{handRaised ? "Lower hand" : "Raise hand"}</span>
            </button>
          )}

          <button
            onClick={leave}
            className="inline-flex items-center gap-1.5 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{isHost ? "End session" : "Leave"}</span>
          </button>
        </div>
      </header>

      <div className="flex-1 flex relative">
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
          <div
            className={`relative rounded-xl border-2 transition-colors ${
              speaking
                ? "border-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,0.25)]"
                : "border-slate-700"
            }`}
          >
            {isHost ? (
              <video
                ref={localVideoRef}
                autoPlay
                muted
                playsInline
                className="max-h-[70vh] max-w-full rounded-lg bg-black"
              />
            ) : (
              <video
                ref={remoteVideoRef}
                autoPlay
                playsInline
                className="max-h-[70vh] max-w-full rounded-lg bg-black"
              />
            )}
            {!connected && !reconnectGivenUp && reconnectAttempts === 0 && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/60 rounded-lg">
                <div className="text-center">
                  <Loader2 className="w-8 h-8 text-white/80 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-white/80 font-medium">Connecting to classroom…</p>
                </div>
              </div>
            )}
            {recording && (
              <span className="absolute top-3 left-3 sm:hidden inline-flex items-center gap-1 bg-rose-600/90 text-white text-[10px] font-bold uppercase px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                REC
              </span>
            )}
          </div>
        </div>

        {isHost && (
          <>
            <aside className="hidden lg:flex w-72 flex-shrink-0 border-l border-slate-800 bg-slate-950/50">
              <ParticipantsPanel
                participants={viewerList.map(toParticipant)}
                onMute={muteViewer}
                onKick={kickViewer}
                onMuteAll={muteAll}
                onUnmuteAll={unmuteAll}
              />
            </aside>
            {showParticipants && (
              <div
                className="lg:hidden fixed inset-0 z-30 flex"
                onClick={() => setShowParticipants(false)}
              >
                <div className="flex-1 bg-slate-950/60" />
                <div
                  className="w-80 max-w-[85vw] bg-slate-950 border-l border-slate-800"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ParticipantsPanel
                    participants={viewerList.map(toParticipant)}
                    onMute={muteViewer}
                    onKick={kickViewer}
                    onMuteAll={muteAll}
                    onUnmuteAll={unmuteAll}
                    onClose={() => setShowParticipants(false)}
                    isMobile
                  />
                </div>
              </div>
            )}
          </>
        )}

        <ReconnectOverlay attempts={reconnectAttempts} givenUp={reconnectGivenUp} />
      </div>

      <footer className="px-4 sm:px-6 py-2 border-t border-slate-800 text-xs text-slate-400 truncate">
        {status}
      </footer>

      {showAnalytics && (
        <AnalyticsModal sessionId={sessionId} onClose={() => setShowAnalytics(false)} />
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function toParticipant(v: {
  user_id: string;
  name: string;
  handRaised: boolean;
  muted: boolean;
}): ParticipantInfo {
  return { ...v };
}

function fmtMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function safeParse(raw: string): any {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function tierRankForDisplay(t: QualityTier): number {
  return t === "audio" ? 0 : t === "low" ? 1 : t === "sd" ? 2 : 3;
}

function tierIsLower(a: QualityTier, b: QualityTier): boolean {
  return tierRankForDisplay(a) < tierRankForDisplay(b);
}

function fmtSeconds(s: number | null | undefined): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}m ${r}s` : `${r}s`;
}

function AnalyticsModal({ sessionId, onClose }: { sessionId: string; onClose: () => void }) {
  const { data, isLoading } = useLiveAnalytics(sessionId, true);

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 flex items-center justify-center px-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        <header className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-brand-400" />
            <h2 className="text-sm font-bold">Session analytics</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-800 text-slate-400"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="p-5 overflow-y-auto flex-1">
          {isLoading || !data ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
                <Stat label="Unique viewers" value={String(data.unique_viewers)} />
                <Stat label="Total joins" value={String(data.total_joins)} />
                <Stat label="Peak concurrent" value={String(data.peak_viewer_count)} />
                <Stat label="Avg. watch time" value={fmtSeconds(data.average_watch_seconds)} />
              </div>

              <h3 className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-2">
                Attendance
              </h3>
              {data.attendees.length === 0 ? (
                <p className="text-xs text-slate-500">No attendance rows yet.</p>
              ) : (
                <div className="bg-slate-950/50 border border-slate-800 rounded-lg divide-y divide-slate-800">
                  {data.attendees.map((a, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2 text-xs">
                      <span className="font-medium text-slate-200 truncate">
                        {a.user_name || a.user_id.slice(0, 8)}
                      </span>
                      <span className="flex items-center gap-3 text-slate-400">
                        <span>joined {new Date(a.joined_at).toLocaleTimeString()}</span>
                        <span>{fmtSeconds(a.duration_seconds)}</span>
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-lg p-3">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-lg font-bold text-white mt-0.5">{value}</p>
    </div>
  );
}
