import { PageSkeleton } from "@/components/loading/Skeleton";

/**
 * Route-segment fallback. Next.js shows this while a /dashboard/* chunk is
 * fetching — on first nav to a module the user has never opened. Purely
 * visual; React Query still manages data-state skeletons inside the page.
 */
export default function DashboardLoading() {
  return <PageSkeleton />;
}
