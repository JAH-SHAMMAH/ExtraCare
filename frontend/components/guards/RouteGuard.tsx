"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { permissionForPath, canAccessPath } from "@/lib/access";

/**
 * Authorization guard for the dashboard subtree (Phase 7 RBAC).
 *
 * Authentication is already enforced by `middleware.ts` (token presence) and
 * the dashboard layout (splash + redirect). This guard adds the missing layer:
 * AUTHORIZATION by URL. It looks the current path up in the shared access map
 * (the SAME table that hides sidebar links) and, if the signed-in user lacks
 * the required permission, renders an Unauthorized panel instead of the page.
 *
 * Because the sidebar and this guard read one source of truth, a hidden link
 * can never be reached by typing the URL — closing the "UI-hidden but
 * directly-navigable" gap the audit flagged.
 */
export function RouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, hasPermission } = useAuthStore();
  const required = permissionForPath(pathname);

  // While the auth store is still hydrating, `user` is null — render children;
  // the layout is showing a splash anyway, and the check re-runs once the user
  // (with permissions) is available.
  if (required && user && !canAccessPath(pathname, hasPermission)) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-400 px-8">
        <ShieldAlert size={44} className="mb-4 opacity-40" />
        <p className="font-semibold text-slate-700 text-lg">Unauthorized</p>
        <p className="text-sm mt-1 text-center max-w-md">
          You don&apos;t have permission to view this page. If you think this is a
          mistake, contact your administrator.
        </p>
        <p className="text-xs text-slate-400 mt-2 font-mono">Required: {required}</p>
        <Link
          href="/dashboard"
          className="mt-6 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
        >
          Back to Dashboard
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
