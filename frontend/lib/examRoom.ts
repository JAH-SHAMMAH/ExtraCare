/** Inactivity limit in the student exam room: after 3 minutes with no mouse, keyboard
 *  or touch activity the student gets a warning message. */
export const IDLE_LIMIT_MS = 3 * 60 * 1000;

export function isIdle(now: number, lastActive: number, limit = IDLE_LIMIT_MS): boolean {
  return now - lastActive >= limit;
}

/** Collapses the several browser events one tab-switch fires into a single count. */
export function makeDebounce(ms = 1500) {
  let last = 0;
  return () => {
    const now = Date.now();
    if (now - last < ms) return false;
    last = now;
    return true;
  };
}
