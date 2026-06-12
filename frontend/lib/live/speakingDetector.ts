// Speaking detector — wraps a MediaStream in an AudioContext + AnalyserNode
// and emits a boolean "isSpeaking" state. Uses RMS of the time-domain signal
// vs a threshold with a short trailing hold so the indicator doesn't flicker
// on every silent gap between words.

export interface SpeakingDetectorOptions {
  threshold?: number; // 0–1 RMS threshold. 0.03 = quiet room baseline.
  pollMs?: number; // Sampling cadence. 150ms = 6 updates/sec, cheap.
  holdMs?: number; // How long to keep "speaking" true after dipping below threshold.
  onChange: (speaking: boolean) => void;
}

export interface SpeakingDetector {
  stop: () => void;
  isSpeaking: () => boolean;
}

export function createSpeakingDetector(
  stream: MediaStream,
  options: SpeakingDetectorOptions,
): SpeakingDetector | null {
  const audioTracks = stream.getAudioTracks();
  if (audioTracks.length === 0) return null;

  const threshold = options.threshold ?? 0.03;
  const pollMs = options.pollMs ?? 150;
  const holdMs = options.holdMs ?? 700;

  let Ctx: typeof AudioContext | undefined;
  if (typeof window !== "undefined") {
    Ctx = window.AudioContext || (window as any).webkitAudioContext;
  }
  if (!Ctx) return null;

  let ctx: AudioContext;
  try {
    ctx = new Ctx();
  } catch {
    return null;
  }

  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  analyser.smoothingTimeConstant = 0.5;
  source.connect(analyser);

  const buffer = new Uint8Array(analyser.fftSize);
  let speaking = false;
  let lastAboveThreshold = 0;
  let stopped = false;

  const tick = () => {
    if (stopped) return;
    analyser.getByteTimeDomainData(buffer);
    // RMS of the 0..255 signal, normalised to 0..1 around the 128 midpoint.
    let sum = 0;
    for (let i = 0; i < buffer.length; i++) {
      const v = (buffer[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / buffer.length);

    const now = Date.now();
    if (rms >= threshold) lastAboveThreshold = now;
    const nextSpeaking = now - lastAboveThreshold <= holdMs;
    if (nextSpeaking !== speaking) {
      speaking = nextSpeaking;
      options.onChange(speaking);
    }
  };

  const interval = setInterval(tick, pollMs);

  return {
    stop: () => {
      stopped = true;
      clearInterval(interval);
      try {
        source.disconnect();
      } catch {
        // already disconnected
      }
      ctx.close().catch(() => {});
    },
    isSpeaking: () => speaking,
  };
}
