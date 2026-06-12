"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { meApi } from "@/lib/api";
import { useAuthStore, type ActiveRole } from "@/lib/store";
import { moduleAllowedForOrg } from "@/lib/workspace";

// ── Types ────────────────────────────────────────────────────────────────────
// Mirrors the /me/contexts response shape. Fields are kept loose (unknown/
// optional) so a backend change can't crash the dashboard — components deal
// with nulls via `?.` and safe fallbacks.

export interface ContextClass {
  id: string;
  name: string;
  level: string | null;
  academic_year: string | null;
  room: string | null;
}

export interface ContextSubject {
  id: string;
  name: string;
  code: string | null;
}

export interface ContextSlot {
  id: string;
  class_id: string;
  subject_id: string | null;
  subject_name: string | null;
  day_of_week: number; // 0=Mon..6=Sun
  start_time: string;
  end_time: string;
  room: string | null;
  teacher_id: string | null;
}

export interface TeacherContext {
  classes: ContextClass[];
  subjects: ContextSubject[];
  timetable: ContextSlot[];
  today_slots: ContextSlot[];
  stats: {
    classes_count: number;
    subjects_count: number;
    today_lessons: number;
    pending_grades: number;
  };
}

export interface StudentContext {
  student: {
    id: string;
    student_id: string;
    first_name: string;
    last_name: string;
    photo_url: string | null;
    class_id: string | null;
  };
  class: ContextClass | null;
  timetable: ContextSlot[];
  today_slots: ContextSlot[];
  stats: {
    attendance_pct: number | null;
    attendance_days: number;
    pending_assignments: number;
  };
}

export interface ParentChild {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  photo_url: string | null;
  class_id: string | null;
  class_name: string | null;
  relationship: string;
  is_primary: boolean;
  stats: {
    attendance_pct: number | null;
    pending_assignments: number;
    latest_grade_letter: string | null;
    latest_grade_score: number | null;
  };
}

export interface ParentContext {
  children: ParentChild[];
}

export interface MyContexts {
  user_id: string;
  roles: string[];
  available_roles: ActiveRole[];
  default_role: ActiveRole;
  as_admin: { is_admin: true } | null;
  as_teacher: TeacherContext | null;
  as_parent: ParentContext | null;
  as_student: StudentContext | null;
}

// ── Hook ─────────────────────────────────────────────────────────────────────

/**
 * Fetches `/me/contexts` and keeps the auth-store's `activeRole` in sync with
 * what the user can actually do. Rules:
 *
 *   1. If no `activeRole` is persisted → adopt the server-chosen `default_role`.
 *   2. If persisted role is no longer in `available_roles` (e.g. parent link
 *      was removed) → snap back to `default_role` so the sidebar doesn't
 *      render a stale/empty filter.
 */
export function useMyContexts() {
  const { activeRole, setActiveRole, isAuthenticated, org } = useAuthStore();
  const schoolEnabled = !!org && moduleAllowedForOrg(org, "school");

  const query = useQuery<MyContexts>({
    queryKey: ["me", "contexts"],
    queryFn: meApi.contexts,
    // Only makes sense on a school tenant — hospital/business orgs don't
    // expose the multi-role home pages.
    enabled: isAuthenticated && schoolEnabled,
    // Linkage changes rarely. 60s is a comfortable cache without feeling stale.
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!query.data) return;
    const { available_roles, default_role } = query.data;
    if (!activeRole) {
      setActiveRole(default_role);
      return;
    }
    if (!available_roles.includes(activeRole)) {
      setActiveRole(default_role);
    }
  }, [query.data, activeRole, setActiveRole]);

  return query;
}

/** Convenience: the subset of the response for the currently active role. */
export function useActiveRoleContext(): {
  activeRole: ActiveRole | null;
  context: TeacherContext | StudentContext | ParentContext | null;
  isAdmin: boolean;
} {
  const { activeRole } = useAuthStore();
  const { data } = useMyContexts();

  if (!data || !activeRole) return { activeRole, context: null, isAdmin: false };

  if (activeRole === "admin") return { activeRole, context: null, isAdmin: !!data.as_admin };
  if (activeRole === "teacher") return { activeRole, context: data.as_teacher, isAdmin: false };
  if (activeRole === "parent") return { activeRole, context: data.as_parent, isAdmin: false };
  if (activeRole === "student") return { activeRole, context: data.as_student, isAdmin: false };
  return { activeRole, context: null, isAdmin: false };
}
