import Link from "next/link";
import { Construction, ArrowUpRight } from "lucide-react";

/**
 * Clean, honest placeholder for a nav item that's wired into the sidebar but
 * whose backend isn't built yet. It LOADS (never 404s) and clearly says the
 * feature is planned — so it's never mistaken for a finished page. `action`
 * optionally links to real, existing functionality that overlaps.
 */
export function PlannedFeature({
  section, title, description, points, action,
}: {
  section: string;
  title: string;
  description: string;
  points?: string[];
  action?: { href: string; label: string };
}) {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <nav className="flex items-center gap-2 text-xs text-slate-400 mb-2">
        <span>{section}</span><span>/</span>
        <span className="text-brand-600 font-semibold">{title}</span>
      </nav>
      <h1 className="text-2xl font-black text-slate-900 tracking-tight mb-6">{title}</h1>

      <div className="bg-white rounded-xl border border-slate-200 p-8">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-11 h-11 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 shrink-0">
            <Construction size={22} />
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900">Planned — not yet available</p>
            <p className="text-xs text-slate-500">This screen is reserved in the menu; the feature is on the roadmap.</p>
          </div>
        </div>

        <p className="text-sm text-slate-600 leading-relaxed">{description}</p>

        {points && points.length > 0 && (
          <ul className="mt-4 space-y-1.5">
            {points.map((p) => (
              <li key={p} className="text-sm text-slate-600 flex items-start gap-2">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-brand-400 shrink-0" />{p}
              </li>
            ))}
          </ul>
        )}

        {action && (
          <Link href={action.href} className="mt-6 inline-flex items-center gap-1.5 btn-secondary">
            {action.label} <ArrowUpRight size={14} />
          </Link>
        )}
      </div>
    </div>
  );
}
