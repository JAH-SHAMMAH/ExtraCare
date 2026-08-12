# Backend Own-Record Gates Checklist

## Status: MIGRATION 121 + SCOPE CHANGES COMPLETE
The migration narrows the student role permissions. This document tracks which backends need own-record enforcement gates.

## Scope-by-Scope Backend Gate Status

### Core Personal Access (Own Records Only)

| Scope | Endpoint | Backend Gate | Status | Notes |
|-------|----------|--------------|--------|-------|
| `school:timetable:read` | `/timetable` | Fetch `current_user.student.class_id` only | ⏳ TODO | New scope, needs gate |
| `school:library:read` | `/library` | Fetch `current_user.student.id` loan records only | ⏳ TODO | Existing scope, gate needed |
| `school:reports:read` | `/report-card` | Fetch `current_user.student.id` report only | ✅ DONE (mig 01f6fe8) | Own-record + publish gate added |
| `school:classroom:read` | `/eclassroom` (assignments) | Fetch `current_user.student.class_id` assignments only | ⏳ TODO | Existing scope, gate needed |
| `school:journals:read` | `/journals` | Fetch `current_user.student.id` journals only | ⏳ TODO | Verify existing scope doesn't leak |
| `school:lessons:read` | `/lessons` | Fetch lessons assigned to student's class | ⏳ TODO | Verify scope enforcement |

### Student-Specific Engagement

| Scope | Endpoint | Backend Gate | Status | Notes |
|-------|----------|--------------|--------|-------|
| `school:cbt:sit` | `/cbt` | Fetch exams assigned to `current_user.student.id` only; allow sit/submit only (not manage) | ⏳ TODO | NEW SCOPE — needs full gating logic |
| `school:clubs:read` | `/clubs` | Fetch clubs + allow enrollment (ownership at club-student junction) | ⏳ TODO | Verify existing scope is student-scoped |
| `school:feedback:read` | `/feedback` | Allow submit feedback (write action gated server-side) | ⏳ TODO | Verify scope only allows submission, not viewing others' |
| `school:voting:submit` | `/voting` | Allow cast vote/rate for teacher only (ownership check) | ⏳ TODO | NEW SCOPE — rename from school:voting:read |

### Housekeeping

| Scope | Endpoint | Backend Gate | Status | Notes |
|-------|----------|--------------|--------|-------|
| `users:read` | `/profile` (self) | Fetch `current_user` profile only | ✅ DONE | Already personal endpoint |

---

## Critical Path (Must Have Before Redeploy)

1. ✅ Migration 121 created and tested
2. ✅ Student role preset updated in models/role.py
3. ⏳ **PENDING**: Ensure `/report-card` gates from mig 01f6fe8 are actually enforced
4. ⏳ **PENDING**: Build `school:cbt:sit` gate for `/cbt` endpoints (sit vs. manage split)
5. ⏳ **PENDING**: Update access.ts to recognize `school:cbt:sit` instead of `school:cbt:read`

## Deferred (Can Follow in Patch)

- Timetable own-record gate (lower priority, less sensitive)
- Library own-record gate
- Classwork own-record gate
- Feedback scope enforcement
- Voting scope rename (May need separate migration if updating existing vote records)

## Test Coverage Needed

- ✅ Existing tests for teacher RBAC (migration 118) should pass unmodified
- ⏳ New tests for student own-record gates (each scope above)
- ⏳ Regression tests for students with narrow scopes not reaching admin surfaces

