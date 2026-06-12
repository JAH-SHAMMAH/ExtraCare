// Adaptive bitrate controller — samples RTCPeerConnection.getStats() and
// recommends a quality tier based on packet loss + round-trip time.
// Called on an interval (~3s) per peer; its output feeds rtcHelpers.applyEncodingParams.

import type { QualityTier } from "./encodingTiers";

export interface NetworkSample {
  packetLossPct: number; // 0–100
  rttMs: number; // round-trip time in milliseconds
  timestamp: number;
}

export interface AdaptiveState {
  lastSample?: NetworkSample;
  // Running counters to compute packet loss delta between polls.
  lastPacketsSent?: number;
  lastPacketsLost?: number;
  // Hysteresis — number of consecutive "bad" samples before downgrading, so
  // a single glitch doesn't bounce quality.
  consecutiveBad: number;
  consecutiveGood: number;
  currentTier: QualityTier;
}

export function createAdaptiveState(initialTier: QualityTier): AdaptiveState {
  return { consecutiveBad: 0, consecutiveGood: 0, currentTier: initialTier };
}

// Pull a NetworkSample out of a getStats report. Returns null if the report
// doesn't have enough outbound-rtp data yet (first poll on a fresh peer).
export function sampleFromStats(
  report: RTCStatsReport,
  state: AdaptiveState,
): NetworkSample | null {
  let packetsSent = 0;
  let packetsLost = 0;
  let rttMs = 0;
  let sawOutbound = false;

  report.forEach((s: any) => {
    if (s.type === "outbound-rtp" && s.kind === "video") {
      packetsSent += s.packetsSent ?? 0;
      sawOutbound = true;
    }
    if (s.type === "remote-inbound-rtp" && s.kind === "video") {
      packetsLost += s.packetsLost ?? 0;
      if (typeof s.roundTripTime === "number") {
        rttMs = Math.max(rttMs, s.roundTripTime * 1000);
      }
    }
    if (s.type === "candidate-pair" && s.state === "succeeded" && s.nominated) {
      if (typeof s.currentRoundTripTime === "number") {
        rttMs = Math.max(rttMs, s.currentRoundTripTime * 1000);
      }
    }
  });

  if (!sawOutbound) return null;

  const deltaSent =
    state.lastPacketsSent !== undefined ? packetsSent - state.lastPacketsSent : 0;
  const deltaLost =
    state.lastPacketsLost !== undefined ? packetsLost - state.lastPacketsLost : 0;

  state.lastPacketsSent = packetsSent;
  state.lastPacketsLost = packetsLost;

  const lossPct = deltaSent > 0 ? (deltaLost / (deltaSent + deltaLost)) * 100 : 0;

  return {
    packetLossPct: Math.max(0, Math.min(100, lossPct)),
    rttMs,
    timestamp: Date.now(),
  };
}

// Pure tier recommendation: map sample → desired tier.
// Thresholds chosen from WebRTC quality guidance (Google-published SLOs):
//   <2% loss + <200ms RTT → healthy
//   2–5% loss or 200–400ms → degrade one step
//   5–10% loss or 400–800ms → degrade further
//   >10% loss or >800ms → audio-only
export function recommendTier(sample: NetworkSample, currentTier: QualityTier): QualityTier {
  const { packetLossPct, rttMs } = sample;

  if (packetLossPct > 10 || rttMs > 800) return "audio";
  if (packetLossPct > 5 || rttMs > 400) {
    return currentTier === "hd" ? "low" : currentTier === "sd" ? "low" : "low";
  }
  if (packetLossPct > 2 || rttMs > 200) {
    return currentTier === "hd" ? "sd" : currentTier;
  }
  // Healthy — allow upgrade by one step (adaptive recovery).
  return currentTier === "audio"
    ? "low"
    : currentTier === "low"
    ? "sd"
    : currentTier === "sd"
    ? "hd"
    : "hd";
}

// Hysteresis wrapper: require N consecutive same-direction samples before
// actually changing tier. Prevents thrashing on transient network blips.
export function updateTierWithHysteresis(
  state: AdaptiveState,
  sample: NetworkSample,
  options: { downThreshold?: number; upThreshold?: number } = {},
): QualityTier {
  const downThreshold = options.downThreshold ?? 2;
  const upThreshold = options.upThreshold ?? 4;
  const recommended = recommendTier(sample, state.currentTier);

  state.lastSample = sample;

  if (recommended === state.currentTier) {
    state.consecutiveBad = 0;
    state.consecutiveGood = 0;
    return state.currentTier;
  }

  const isDowngrade = tierRank(recommended) < tierRank(state.currentTier);
  if (isDowngrade) {
    state.consecutiveBad += 1;
    state.consecutiveGood = 0;
    if (state.consecutiveBad >= downThreshold) {
      state.currentTier = recommended;
      state.consecutiveBad = 0;
    }
  } else {
    state.consecutiveGood += 1;
    state.consecutiveBad = 0;
    if (state.consecutiveGood >= upThreshold) {
      state.currentTier = recommended;
      state.consecutiveGood = 0;
    }
  }

  return state.currentTier;
}

function tierRank(t: QualityTier): number {
  return t === "audio" ? 0 : t === "low" ? 1 : t === "sd" ? 2 : 3;
}
