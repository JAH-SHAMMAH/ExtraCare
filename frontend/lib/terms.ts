// Canonical academic term values — ONE source of truth so exam creation, the
// Result Publish helper, grade entry, and the parent report card all agree.
// (Fees use their own term1/term2/term3 code scheme for a separate flow.)
//
// These strings are COMPARED BY VALUE against what the database stores. The
// backend filters `Grade.term == term`, `ReportApproval.term`, `CBTExam.term`
// and others by exact name, so this list and `academic_terms.name` must say the
// same thing. When they disagree nothing errors — queries simply match nothing,
// and a parent opens an empty report card.
//
// That is not hypothetical: these read "Term 1/2/3" while the school's terms had
// been renamed to Autumn/Spring/Summer, and every parent report card came back
// empty until this file caught up. Changing a term in Report Setup means
// changing it here too, until the follow-up below removes the duplication.
//
// FOLLOW-UP: drive these from GET /platform/academic-terms so the list cannot
// drift from the database at all. See docs/future-features.md section 6 — this
// file is the frontend half of the same free-text-term problem.
export const TERMS = ["Autumn", "Spring", "Summer"] as const;
export type Term = (typeof TERMS)[number];
export const DEFAULT_TERM: Term = "Autumn";
