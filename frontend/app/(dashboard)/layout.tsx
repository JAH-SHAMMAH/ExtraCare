"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { RouteGuard } from "@/components/guards/RouteGuard";
import { Splash } from "@/components/loading/Splash";
import { TopProgress } from "@/components/loading/TopProgress";
import { useAuthStore } from "@/lib/store";
import { useMe } from "@/hooks/useAuth";
import { markNavPainted } from "@/lib/perf";
import { doneProgress } from "@/lib/progress";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isAuthenticated, user } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  // Re-sync identity + permissions from the server on dashboard load. Without
  // this the auth store only ever holds the permission set captured at LOGIN
  // (persisted to localStorage), so a role/permission change never takes effect
  // until a manual logout/login. `useMe` is gated on isAuthenticated and cached
  // for 5 min (staleTime), so a full reload refetches while in-session client
  // navigation stays cheap. It also soft-logs-out on identity/module drift.
  useMe();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  // Force-change enforcement: if an admin reset this account, block the app until
  // the user sets a new password. The change-password page itself stays reachable.
  useEffect(() => {
    if (mounted && isAuthenticated && user?.force_password_change && pathname !== "/dashboard/change-password") {
      router.replace("/dashboard/change-password");
    }
  }, [mounted, isAuthenticated, user?.force_password_change, pathname, router]);

  // Close the nav-timing bracket opened by Sidebar's markNavClick. Fires
  // after the route's children commit, so the measurement reflects "click
  // → something painted" rather than "click → route change announced".
  // Also belt-and-braces closes the progress bar (markNavPainted does this
  // itself, but back/forward nav may skip markNavClick entirely).
  useEffect(() => {
    markNavPainted(pathname);
    doneProgress();
    setSidebarOpen(false);   // close the mobile drawer on navigation
  }, [pathname]);

  // Close the mobile drawer on Escape.
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setSidebarOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sidebarOpen]);

  // Before mount, render a branded splash — avoids SSR/client mismatch from
  // the persisted store and gives the user something coherent while the
  // auth store hydrates.
  if (!mounted) return <Splash />;

  if (!isAuthenticated) return <Splash label="Redirecting to sign in" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <TopProgress />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <TopBar onMenu={() => setSidebarOpen(true)} />
      <main className="ml-0 lg:ml-64 mt-16 min-h-[calc(100vh-64px)] animate-fade-in">
        <ErrorBoundary>
          <RouteGuard>{children}</RouteGuard>
        </ErrorBoundary>
      </main>
    </div>
  );
}
