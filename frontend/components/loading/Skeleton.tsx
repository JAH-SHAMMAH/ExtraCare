"use client";

import { cn } from "@/lib/utils";
import type { CSSProperties } from "react";

/**
 * Skeleton primitive. Renders a shimmering placeholder block that respects
 * prefers-reduced-motion (flat neutral fill when the user opts out).
 *
 * Prefer the composed variants below for typical shapes — they guarantee
 * the same rhythm across the app (page headers, tables, metric cards, etc).
 */
export function Skeleton({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <div className={cn("skeleton", className)} style={style} aria-hidden />;
}

export function SkeletonLine({
  className,
  style,
}: {
  className?: string;
  style?: CSSProperties;
}) {
  return <Skeleton className={cn("h-3", className)} style={style} />;
}

export function SkeletonCircle({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <Skeleton
      className={cn("rounded-full shrink-0", className)}
      style={{ width: size, height: size }}
    />
  );
}

/**
 * Typical page-header placeholder: breadcrumb, title, subtitle.
 */
export function PageHeaderSkeleton() {
  return (
    <div className="mb-8 space-y-2">
      <Skeleton className="h-2.5 w-24" />
      <Skeleton className="h-7 w-64 rounded-lg" />
      <Skeleton className="h-3 w-80" />
    </div>
  );
}

/**
 * 4-up metric card grid skeleton. Matches `MetricsGrid` rhythm.
 */
export function CardGridSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-white rounded-xl border border-slate-200/70 p-5 shadow-sm"
        >
          <div className="flex items-start justify-between mb-4">
            <Skeleton className="w-9 h-9 rounded-lg" />
            <Skeleton className="h-4 w-10 rounded-full" />
          </div>
          <Skeleton className="h-7 w-24 rounded-lg mb-2" />
          <Skeleton className="h-2.5 w-28" />
        </div>
      ))}
    </div>
  );
}

/**
 * Data-table placeholder. Pass `cols` to match the real table layout so
 * the transition from skeleton → data doesn't shift columns.
 */
export function TableSkeleton({
  rows = 8,
  cols = 5,
  withHeader = true,
}: {
  rows?: number;
  cols?: number;
  withHeader?: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {withHeader && (
        <div className="px-5 py-4 border-b border-slate-100 flex gap-4">
          {Array.from({ length: cols }).map((_, i) => (
            <Skeleton key={i} className="h-2.5 flex-1 max-w-[120px]" />
          ))}
        </div>
      )}
      <div className="divide-y divide-slate-50">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="px-5 py-4 flex gap-4 items-center">
            {Array.from({ length: cols }).map((_, c) => {
              const max = c === 0 ? 160 : c === cols - 1 ? 80 : 200;
              return (
                <Skeleton
                  key={c}
                  className="h-3 flex-1"
                  style={{ maxWidth: max }}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Vertical list placeholder (feed, notifications, activity rows).
 */
export function ListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden divide-y divide-slate-50">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="px-5 py-3.5 flex items-start gap-3">
          <SkeletonCircle size={28} />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-2.5 w-56" />
          </div>
          <Skeleton className="h-2.5 w-12" />
        </div>
      ))}
    </div>
  );
}

/**
 * Full-page skeleton frame: header + metrics + two content columns.
 * Used by `loading.tsx` segments so cold-cached navigations get a
 * coherent shell instantly.
 */
export function PageSkeleton() {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <PageHeaderSkeleton />
      <CardGridSkeleton />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-8">
        <div className="lg:col-span-2">
          <ListSkeleton rows={6} />
        </div>
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-8 w-full rounded-lg" />
            <Skeleton className="h-8 w-full rounded-lg" />
            <Skeleton className="h-8 w-full rounded-lg" />
          </div>
        </div>
      </div>
    </div>
  );
}
