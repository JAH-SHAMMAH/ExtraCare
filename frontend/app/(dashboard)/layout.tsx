"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Splash } from "@/components/loading/Splash";
import { TopProgress } from "@/components/loading/TopProgress";
import { useAuthStore } from "@/lib/store";
import { markNavPainted } from "@/lib/perf";
import { doneProgress } from "@/lib/progress";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const { isAuthenticated } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !isAuthenticated) {
      router.replace("/login");
    }
  }, [mounted, isAuthenticated, router]);

  // Close the nav-timing bracket opened by Sidebar's markNavClick. Fires
  // after the route's children commit, so the measurement reflects "click
  // → something painted" rather than "click → route change announced".
  // Also belt-and-braces closes the progress bar (markNavPainted does this
  // itself, but back/forward nav may skip markNavClick entirely).
  useEffect(() => {
    markNavPainted(pathname);
    doneProgress();
  }, [pathname]);

  // Before mount, render a branded splash — avoids SSR/client mismatch from
  // the persisted store and gives the user something coherent while the
  // auth store hydrates.
  if (!mounted) return <Splash />;

  if (!isAuthenticated) return <Splash label="Redirecting to sign in" />;

  return (
    <div className="min-h-screen bg-slate-50">
      <TopProgress />
      <Sidebar />
      <TopBar />
      <main className="ml-64 mt-16 min-h-[calc(100vh-64px)] animate-fade-in">
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
    </div>
  );
}
