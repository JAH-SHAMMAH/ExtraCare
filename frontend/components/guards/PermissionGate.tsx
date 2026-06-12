"use client";

import { useAuthStore } from "@/lib/store";
import { ShieldAlert } from "lucide-react";

interface PermissionGateProps {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function PermissionGate({ permission, children, fallback }: PermissionGateProps) {
  const { hasPermission } = useAuthStore();

  if (!hasPermission(permission)) {
    return fallback ?? (
      <div className="flex flex-col items-center justify-center py-20 text-slate-400">
        <ShieldAlert size={40} className="mb-3 opacity-40" />
        <p className="font-semibold text-slate-600">Access Denied</p>
        <p className="text-sm mt-1">You don&apos;t have permission to view this content.</p>
      </div>
    );
  }

  return <>{children}</>;
}

export function useHasPermission(permission: string): boolean {
  const { hasPermission } = useAuthStore();
  return hasPermission(permission);
}
