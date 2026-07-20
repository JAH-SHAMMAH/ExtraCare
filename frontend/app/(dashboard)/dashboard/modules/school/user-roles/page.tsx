import { redirect } from "next/navigation";

// Consolidated: role management has one home — Roles & Permissions. This former
// duplicate surface now redirects there. Admin password reset lives on the
// Users page (per-user action).
export default function UserRolesPage() {
  redirect("/dashboard/hrm/roles");
}
