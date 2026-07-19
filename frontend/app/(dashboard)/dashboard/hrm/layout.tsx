import { HrTabNav } from "@/components/hrm/HrTabNav";

/**
 * HR Manager shell — renders the Educare-style click-to-expand tab bar above
 * every /hrm page. The nav filters itself by the viewer's HR permissions, so
 * regular staff see only their self-service tabs and HR/admin see the full set.
 */
export default function HrmLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <div className="px-8 pt-8 max-w-6xl mx-auto w-full">
        <HrTabNav />
      </div>
      {children}
    </div>
  );
}
