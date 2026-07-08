// Canonical academic term values — ONE source of truth so exam creation, the
// Result Publish helper, grade entry, and the parent report card all agree.
// (Fees use their own term1/term2/term3 code scheme for a separate flow.)
export const TERMS = ["Term 1", "Term 2", "Term 3"] as const;
export type Term = (typeof TERMS)[number];
export const DEFAULT_TERM: Term = "Term 1";
