"use client";

import { useAuthStore } from "@/lib/store";
import { useMyContexts } from "@/hooks/useMyContexts";
import { useDelayedFlag } from "@/hooks/useDelayedFlag";
import { PageSkeleton } from "@/components/loading/Skeleton";
import { moduleAllowedForOrg } from "@/lib/workspace";
import { AdminHome, OnboardingEmptyState } from "./home/AdminHome";
import { TeacherHome } from "./home/TeacherHome";
import { StudentHome } from "./home/StudentHome";
import { ParentHome } from "./home/ParentHome";

/**
 * Phase 6.3 — role-scoped home router.
 *
 * The dashboard landing page branches on `activeRole` (persisted in the
 * auth store, seeded by `/me/contexts`). Each branch is a full-screen home
 * component — no shared chrome here on purpose so each role can tune its
 * own rhythm (student's hero card, parent's child cards, teacher's today
 * schedule) without fighting a common skeleton.
 *
 * Non-school tenants and pre-6.3 orgs skip the router entirely and render
 * the classic admin home — `useMyContexts` is gated on `modules_enabled`
 * including "school" so hospital/business dashboards are unaffected.
 */
export default function DashboardPage() {
  const { org, activeRole } = useAuthStore();
  const noModules = !!org && (!org.modules_enabled || org.modules_enabled.length === 0);
  const schoolEnabled = !!org && moduleAllowedForOrg(org, "school");

  // Always call the hook — React rules — but it self-gates on schoolEnabled.
  const { isLoading } = useMyContexts();
  const showSkeleton = useDelayedFlag(schoolEnabled && isLoading && !activeRole);

  if (noModules) {
    return <OnboardingEmptyState orgName={org!.name} />;
  }

  // Non-school tenants or contexts that haven't resolved → admin home.
  if (!schoolEnabled) {
    return <AdminHome />;
  }

  // Brief shell while /me/contexts resolves for the very first time so the
  // page doesn't flash the wrong role's home.
  if (showSkeleton) return <PageSkeleton />;

  switch (activeRole) {
    case "teacher": return <TeacherHome />;
    case "student": return <StudentHome />;
    case "parent":  return <ParentHome />;
    case "admin":
    default:        return <AdminHome />;
  }
}
