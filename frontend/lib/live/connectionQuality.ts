// Friendly connection-quality labels derived from the adaptive tier + WS state.
// Kept pure so the UI component is trivial and the mapping is unit-testable.

import type { QualityTier } from "./encodingTiers";

export type ConnectionQualityLevel =
  | "connecting"
  | "reconnecting"
  | "good"
  | "fair"
  | "poor"
  | "audio-only"
  | "offline";

export interface ConnectionQualityInput {
  connected: boolean;
  reconnectAttempts: number;
  tier: QualityTier | null;
}

export interface ConnectionQualityDisplay {
  level: ConnectionQualityLevel;
  label: string;
  description: string;
  tone: "good" | "fair" | "poor" | "neutral";
}

export function describeConnection(input: ConnectionQualityInput): ConnectionQualityDisplay {
  if (input.reconnectAttempts > 0) {
    return {
      level: "reconnecting",
      label: "Reconnecting",
      description: "Signal dropped — reconnecting to the classroom.",
      tone: "poor",
    };
  }
  if (!input.connected) {
    return {
      level: "connecting",
      label: "Connecting",
      description: "Joining the session…",
      tone: "neutral",
    };
  }
  switch (input.tier) {
    case "hd":
      return {
        level: "good",
        label: "Good",
        description: "Clear video and audio.",
        tone: "good",
      };
    case "sd":
      return {
        level: "fair",
        label: "Fair",
        description: "Video reduced to save bandwidth.",
        tone: "fair",
      };
    case "low":
      return {
        level: "poor",
        label: "Poor",
        description: "Low quality — classroom network is stretched.",
        tone: "poor",
      };
    case "audio":
      return {
        level: "audio-only",
        label: "Audio only",
        description: "Video paused to keep audio reliable.",
        tone: "poor",
      };
    default:
      return {
        level: "good",
        label: "Connected",
        description: "Live.",
        tone: "good",
      };
  }
}
