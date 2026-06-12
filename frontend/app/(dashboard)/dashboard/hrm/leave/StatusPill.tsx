import type { LeaveStatus } from "@/types";

export function StatusPill({ status }: { status: LeaveStatus }) {
  const tone: Record<LeaveStatus, string> = {
    pending: "bg-amber-100 text-amber-700",
    approved: "bg-emerald-100 text-emerald-700",
    rejected: "bg-rose-100 text-rose-700",
  };

  return (
    <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full capitalize ${tone[status]}`}>
      {status}
    </span>
  );
}
