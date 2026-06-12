// Exponential-backoff reconnect helper for the signaling WebSocket. Used by
// both host and viewer — on close/error, schedules a reconnect with jittered
// backoff up to a cap, giving up after N attempts.

export interface ReconnectOptions {
  maxAttempts?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  jitterPct?: number;
  onAttempt?: (attempt: number, delayMs: number) => void;
  onGiveUp?: () => void;
}

export interface ReconnectController {
  schedule: () => void;
  reset: () => void;
  cancel: () => void;
  attempts: () => number;
}

export function createReconnectController(
  connect: () => void,
  options: ReconnectOptions = {},
): ReconnectController {
  const maxAttempts = options.maxAttempts ?? 8;
  const baseDelayMs = options.baseDelayMs ?? 500;
  const maxDelayMs = options.maxDelayMs ?? 15_000;
  const jitterPct = options.jitterPct ?? 0.3;

  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const clearTimer = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  };

  return {
    schedule: () => {
      if (attempt >= maxAttempts) {
        options.onGiveUp?.();
        return;
      }
      attempt += 1;
      const exp = Math.min(maxDelayMs, baseDelayMs * 2 ** (attempt - 1));
      const jitter = exp * jitterPct * (Math.random() * 2 - 1);
      const delay = Math.max(100, Math.round(exp + jitter));
      options.onAttempt?.(attempt, delay);
      clearTimer();
      timer = setTimeout(() => {
        timer = null;
        connect();
      }, delay);
    },
    reset: () => {
      attempt = 0;
      clearTimer();
    },
    cancel: () => {
      attempt = maxAttempts;
      clearTimer();
    },
    attempts: () => attempt,
  };
}
