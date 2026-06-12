"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { moduleAllowedForOrg } from "@/lib/workspace";

interface ModuleGateProps {
  module: "school" | "hospital" | "business";
  permission?: string;
  children: React.ReactNode;
}

/**
 * Industry-aware route guard. If the org's workspace does not match this
 * vertical subtree, redirect to /dashboard before rendering the module UI.
 * Permission failures remain visible so operators can diagnose access.
 */
export function ModuleGate({ module, permission, children }: ModuleGateProps) {
  const { org, hasPermission } = useAuthStore();
  const router = useRouter();
  const moduleAllowed = !org || moduleAllowedForOrg(org, module);

  useEffect(() => {
    if (!moduleAllowed) {
      console.warn("[ModuleGate] redirect - module not enabled", {
        module,
        industry: org?.industry,
        enabled: org?.modules_enabled,
      });
      router.replace("/dashboard");
    }
  }, [moduleAllowed, router, module, org?.industry, org?.modules_enabled]);

  if (!moduleAllowed) {
    return null;
  }

  if (permission && !hasPermission(permission)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400 p-8">
        <ShieldAlert size={40} className="mb-3 opacity-40" />
        <p className="font-semibold text-slate-600 text-lg">Access Restricted</p>
        <p className="text-sm mt-1 text-center max-w-md">
          You don&apos;t have permission to access this page.
          Contact your administrator for access.
        </p>
        <p className="text-xs text-slate-400 mt-2 font-mono">Required: {permission}</p>
      </div>
    );
  }

  return <>{children}</>;
}
