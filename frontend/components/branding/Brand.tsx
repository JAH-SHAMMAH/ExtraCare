import { cn } from "@/lib/utils";

/**
 * Fairview School crest, served from `/public`. We use a plain root-relative
 * `<img>` (not a bundler `import`) on purpose: the reference stays valid and the
 * build stays green even before the binary asset is dropped into `frontend/public/`
 * — it simply falls back to the `alt` text until the file is present.
 *
 * Required public assets: logo-navbar-120w.png, logo-navbar-240w.png (header,
 * 1x/2x), logo-square.png (square crest), logo-transparent.png (master).
 */
export function BrandMark({ className, priority }: { className?: string; priority?: boolean }) {
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/logo-navbar-120w.png"
      srcSet="/logo-navbar-120w.png 1x, /logo-navbar-240w.png 2x"
      alt="Fairview School"
      className={cn("w-auto object-contain", className)}
      {...(priority ? { fetchPriority: "high" as const } : {})}
    />
  );
}

/**
 * Document letterhead — the crest atop a printed/Saved-as-PDF document
 * (report cards, invoices, …). Hidden on screen, shown only in print via the
 * `.print-only` rule in globals.css, so it never affects the on-screen layout.
 */
export function PrintLetterhead({ title, subtitle }: { title?: string; subtitle?: string }) {
  return (
    <header className="print-only mb-6 border-b-2 border-brand-600 pb-4">
      <div className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo-square.png" alt="Fairview School" className="h-16 w-16 object-contain" />
        <div>
          <p className="text-xl font-black text-slate-900">Fairview School</p>
          <p className="text-xs font-semibold tracking-wide text-brand-700">Soaring High</p>
        </div>
        {title && (
          <div className="ml-auto text-right">
            <p className="text-lg font-bold text-slate-900">{title}</p>
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
        )}
      </div>
    </header>
  );
}
