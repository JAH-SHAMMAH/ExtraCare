"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 30s fits how mutating this data typically feels — dashboards,
            // list views and table grids. Expensive aggregates (payroll,
            // reports, finance overview, timetable) opt into 60_000 per hook.
            staleTime: 30_000,
            // Keep cached data around for 5 min after a query goes unused so
            // route transitions hydrate instantly from the cache.
            gcTime: 5 * 60 * 1000,
            // Window-focus refetches are disruptive in ERP workflows
            // (a user tabs away for a second and loses their scroll position).
            // Reconnect refetches stay on — useful after losing wifi.
            refetchOnWindowFocus: false,
            refetchOnReconnect: true,
            retry: 1,
          },
          mutations: {
            // Mutations should fail fast — the user is waiting on the UI.
            retry: 0,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="light" enableSystem>
        {children}
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            style: { fontFamily: "Inter, sans-serif", fontSize: "13px" },
          }}
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
