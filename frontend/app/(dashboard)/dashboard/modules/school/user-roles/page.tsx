import { redirect } from "next/navigation";

// Consolidated: role management has one home — Access Control. This former
// duplicate surface now redirects there. Admin password reset lives on the
// Users page (per-user action).
export default function UserRolesPage() {
  redirect("/dashboard/hrm/access-control");
}
