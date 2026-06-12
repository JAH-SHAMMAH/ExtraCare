// Viewer-count-tiered encoding defaults for mesh WebRTC fan-out.
// Host browser pushes N copies of its stream, so per-peer encoding cost
// scales linearly with viewer count. Degrade gracefully as classes grow.

export type QualityTier = "hd" | "sd" | "low" | "audio";

export interface EncodingParams {
  maxBitrate: number; // bits/sec for video sender
  scaleResolutionDownBy: number; // 1 = native, 2 = half, 4 = quarter
  maxFramerate: number;
  audioOnly: boolean;
}

const TIER_PARAMS: Record<QualityTier, EncodingParams> = {
  hd: { maxBitrate: 1_500_000, scaleResolutionDownBy: 1, maxFramerate: 30, audioOnly: false },
  sd: { maxBitrate: 700_000, scaleResolutionDownBy: 1.5, maxFramerate: 24, audioOnly: false },
  low: { maxBitrate: 250_000, scaleResolutionDownBy: 2.5, maxFramerate: 15, audioOnly: false },
  audio: { maxBitrate: 0, scaleResolutionDownBy: 4, maxFramerate: 5, audioOnly: true },
};

// Map viewer count to default encoding tier. Thresholds chosen so a single
// mid-tier laptop host can sustain ~30 viewers without thermal throttling.
export function tierForViewerCount(viewers: number): QualityTier {
  if (viewers <= 5) return "hd";
  if (viewers <= 15) return "sd";
  if (viewers <= 30) return "low";
  return "audio";
}

export function paramsForTier(tier: QualityTier): EncodingParams {
  return TIER_PARAMS[tier];
}

export function paramsForViewerCount(viewers: number): EncodingParams {
  return paramsForTier(tierForViewerCount(viewers));
}
