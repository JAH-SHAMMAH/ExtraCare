import { UserRound } from "lucide-react";
import { cn, resolveMediaUrl } from "@/lib/utils";

/**
 * Student photo. When none has been uploaded yet, a visible placeholder is shown
 * instead, so everyone can see that a photo slot exists and is still empty.
 * Large sizes (64px and up) spell it out: "No photo yet".
 */
export function StudentAvatar({
  name, url, size = 40, className,
}: { name: string; url?: string | null; size?: number; className?: string }) {
  const style = { width: size, height: size };
  if (url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={resolveMediaUrl(url)} alt={name} style={style}
        className={cn("rounded-xl object-cover border border-slate-200 shrink-0", className)} />
    );
  }
  const big = size >= 64;
  return (
    <div style={style} role="img" aria-label={`${name}: no photo uploaded yet`}
      className={cn("rounded-xl bg-gradient-to-b from-slate-100 to-slate-200 border border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 shrink-0 overflow-hidden", className)}>
      {big ? (
        <>
          <UserRound size={Math.round(size * 0.5)} strokeWidth={1.5} aria-hidden />
          <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">No photo yet</span>
        </>
      ) : (
        <UserRound size={Math.max(14, Math.round(size * 0.55))} strokeWidth={1.5} aria-hidden />
      )}
    </div>
  );
}
