import { cn, getInitials, resolveMediaUrl } from "@/lib/utils";

/** Student photo, or initials when there's no picture. */
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
  return (
    <div style={style}
      className={cn("rounded-xl bg-indigo-600/10 border border-indigo-100 flex items-center justify-center text-indigo-700 font-bold shrink-0", className)}>
      <span style={{ fontSize: Math.max(11, size * 0.34) }}>{getInitials(name)}</span>
    </div>
  );
}
